import argparse
import time
import yaml

from src.auth import get_gmail_credentials
from src.state_manager import StateManager
from src.gmail_client import GmailClient
from src.triage_filter import TriageFilter
from src.signal_store import SignalStore


def week_label(date_str: str) -> str:
    """'2025-01-01' -> '2025-W01' (ISO week of the window start)."""
    from datetime import datetime
    d = datetime.strptime(date_str, "%Y-%m-%d")
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be written; do NOT touch Firestore or advance cursor")
    args = parser.parse_args()

    with open("config/config.yaml") as f:
        config = yaml.safe_load(f)

    print("🚀 Initializing pipeline" + (" [DRY-RUN]" if args.dry_run else ""))
    creds = get_gmail_credentials()
    gmail = GmailClient(creds)
    state = StateManager()
    firewall = TriageFilter(config)
    store = SignalStore(config.get("entities", {}))

    start_date, end_date = state.get_date_window(
        days_to_fetch=config["ingestion"]["days_per_batch"]
    )
    week = week_label(start_date)
    print(f"📅 Window {start_date} → {end_date}  ({week})")

    t0 = time.time()
    fetch_limit = config["ingestion"].get("max_fetch_per_run", 500)
    raw_emails = gmail.fetch_batch_by_date(start_date, end_date, limit=fetch_limit)
    print(f"📥 Pulled {len(raw_emails)} raw emails")

    stats = {"fetched": len(raw_emails), "junk_filtered": 0,
             "survivors": 0, "skipped_already_done": 0}

    for email in raw_emails:
        if store.already_processed(email["id"]):
            stats["skipped_already_done"] += 1
            continue
        is_valuable, reason = firewall.evaluate(email)
        if is_valuable:
            store.write_survivor(email, week, dry_run=args.dry_run)
            stats["survivors"] += 1
        else:
            store.write_junk(email, reason, week, dry_run=args.dry_run)
            stats["junk_filtered"] += 1

    stats["duration_s"] = round(time.time() - t0, 1)
    store.write_run(week, stats, dry_run=args.dry_run)

    print(f"\n=== {week} RESULTS ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")

    if args.dry_run:
        print("\n🟡 DRY-RUN: cursor NOT advanced. Re-run without --dry-run to commit.")
    else:
        state.advance_cursor(end_date)
        print(f"\n⏭️ Cursor advanced to {end_date}. ✅")


if __name__ == "__main__":
    main()
