import argparse, os, time, yaml
from datetime import datetime
from src.auth import get_gmail_credentials
from src.state_manager import StateManager
from src.gmail_client import GmailClient
from src.triage_filter import TriageFilter
from src.signal_store import SignalStore
from src.classifier import Classifier
from src.judge import judge_route
from src.corrections import build_corrections_context
import time 
from google.genai.errors import ClientError

def load_config(path="config/config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def week_label(date_str: str) -> str:
    iso = datetime.strptime(date_str, "%Y-%m-%d").isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def stage_ingest(gmail, firewall, store, week, start, end, limit, dry_run) -> dict:
    """INGESTOR agent: fetch a window, firewall it, persist junk + survivors."""
    raw = gmail.fetch_batch_by_date(start, end, limit=limit)
    print(f"📥 Pulled {len(raw)} raw emails")
    s = {"fetched": len(raw), "junk_filtered": 0, "survivors": 0, "skipped": 0}
    for email in raw:
        if store.already_processed(email["id"]):
            s["skipped"] += 1
            continue
        valuable, reason = firewall.evaluate(email)
        if valuable:
            store.write_survivor(email, week, dry_run=dry_run); s["survivors"] += 1
        else:
            store.write_junk(email, reason, week, dry_run=dry_run); s["junk_filtered"] += 1
    return s


def stage_classify(gmail, store, classifier, cfg, dry_run) -> dict:
    """CLASSIFIER + JUDGE (+ CORRECTOR context): brain over the pending queue."""
    threshold = cfg["classifier"]["confidence_threshold"]
    excerpt_len = cfg["classifier"]["body_excerpt_chars"]
    max_corr = cfg["classifier"]["max_corrections_in_prompt"]
    pending = store.get_pending(limit=cfg["ingestion"].get("max_fetch_per_run", 500))
    print(f"🧠 Classifying {len(pending)} survivors...")
    s = {"classified": 0, "needs_review": 0, "llm_tokens": 0}
    for mid, sig in pending:
        body = gmail.get_body_excerpt(mid, excerpt_len)                       # body in
        ctx = build_corrections_context(store, sig.get("sender_ref"), max_corr)  # CORRECTOR context
        result = classify_with_retry(classifier,sig, body, ctx)
        time.sleep(1.0) # CLASSIFIER
        new_status = judge_route(result["confidence"], threshold)                                       # JUDGE
        if dry_run:
            print(f"  [DRY-RUN] {result['category']} ({result['confidence']:.2f}) -> {new_status}  {sig['subject'][:40]}")
            continue
        s["llm_tokens"] += store.save_classification(mid, result, new_status)
        s[new_status] = s.get(new_status, 0) + 1
        if new_status == "classified":
            gmail.apply_label(mid, f"AI/{result['category']}")               # Safe Mode: label only
    s["est_cost_usd"] = round(s["llm_tokens"] / 1_000_000 * 0.30, 4)         # ~Flash input rate
    return s

def classify_with_retry(classifier, sig, body, ctx, max_retries=4):
    for attempt in range(max_retries):
        try:
            return classifier.classify(sig, body, ctx)
        except ClientError as e:
            if e.code == 429 and attempt < max_retries - 1:
                wait = 2 ** attempt * 5   # 5s, 10s, 20s, 40s
                print(f"  429, backing off {wait}s...")
                time.sleep(wait)
            else:
                raise


def run_one_week(gmail, firewall, store, classifier, config, state, dry_run=False) -> dict:
    """Process exactly one cursor window end-to-end: ingest + classify, record
    the run, and advance the cursor — the unit a bulk run repeats.

    Reuses ``stage_ingest`` and ``stage_classify`` verbatim (the actual ingestion
    and classification logic); this wrapper is only the per-week orchestration the
    CLI ``main`` already did inline, factored out so the dashboard's bulk endpoint
    can loop over it without reimplementing the pipeline.

    Idempotent and interrupt-safe: signals are keyed by message_id (re-ingesting a
    window writes nothing new), the run doc is written before the cursor moves,
    and the cursor advances *only* after the week completes — so a crash mid-week
    leaves the cursor where it was and re-running resumes the same window.

    Returns the run ``stats`` enriched with ``week``/``start``/``end`` for the
    caller. The ``stats`` written to the ``runs`` collection keep their original
    shape (no window keys added).
    """
    t0 = time.time()
    limit = config["ingestion"].get("max_fetch_per_run", 500)
    start, end = state.get_date_window(days_to_fetch=config["ingestion"]["days_per_batch"])
    week = week_label(start)
    print(f"📅 {start} → {end}  ({week})")
    stats = stage_ingest(gmail, firewall, store, week, start, end, limit, dry_run)
    print(f"🛡️ ingest: {stats}")
    stats.update(stage_classify(gmail, store, classifier, config, dry_run))
    stats["duration_s"] = round(time.time() - t0, 1)
    store.write_run(week, stats, dry_run=dry_run)
    if not dry_run:
        state.advance_cursor(end)
    return {"week": week, "start": start, "end": end, **stats}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show decisions; write nothing; do not advance cursor")
    parser.add_argument("--classify-only", action="store_true",
                        help="Skip ingest; only drain the existing pending queue (no Gmail fetch, no cursor move)")
    args = parser.parse_args()

    # ---- 1. config + clients (the future orchestrator wiring) ----
    config = load_config()
    print("🚀 Initializing" + (" [DRY-RUN]" if args.dry_run else ""))
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    gmail = GmailClient(get_gmail_credentials())
    state = StateManager()
    firewall = TriageFilter(config.get("triage_filter", {}))
    store = SignalStore(config.get("entities", {}))
    clf_cfg = {**config["classifier"], "seed_interests": config["preferences"]["seed_interests"]}
    classifier = Classifier(project, clf_cfg)

    t0 = time.time()

    # ---- 2. pipeline stages (each = a future agent) ----
    if args.classify_only:
        print("⏭️ classify-only: skipping ingest")
        stats = {"mode": "classify_only"}
        stats.update(stage_classify(gmail, store, classifier, config, args.dry_run))
        stats["duration_s"] = round(time.time() - t0, 1)
        print("\n=== classify-only ===\n  " + "\n  ".join(f"{k}: {v}" for k, v in stats.items()))
        return   # no cursor advance, no run record — this is a re-processing pass

    # ---- 2b. one cursor window (record + advance live inside run_one_week) ----
    result = run_one_week(gmail, firewall, store, classifier, config, state,
                          dry_run=args.dry_run)

    # ---- 3. report ----
    week = result["week"]
    summary = {k: v for k, v in result.items() if k != "week"}
    print(f"\n=== {week} ===\n  " + "\n  ".join(f"{k}: {v}" for k, v in summary.items()))
    if args.dry_run:
        print("\n🟡 DRY-RUN: cursor not advanced.")
    else:
        print(f"⏭️ Cursor → {result['end']} ✅")


if __name__ == "__main__":
    main()