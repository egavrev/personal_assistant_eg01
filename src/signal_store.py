import os
import re
from collections import Counter
from datetime import datetime, timezone
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

# The four fields a human can change in the dashboard review form.
CORRECTABLE_FIELDS = ("category", "topics", "needs_reply", "sender_type")
# Fallback sort key for correction docs whose SERVER_TIMESTAMP hasn't materialised yet.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def parse_sender(raw_sender: str):
    """'GitHub <notifications@github.com>' -> ('notifications@github.com', 'github.com')"""
    match = re.search(r'<([^>]+)>', raw_sender)
    email = (match.group(1) if match else raw_sender).strip().lower()
    domain = email.split('@')[-1] if '@' in email else email
    return email, domain


def resolve_entity(raw_sender: str, entity_config: dict):
    """
    Decision A (domain = identity) + Decision C (exception lists).
    Returns (entity_id, entity_type, display_name, domain).
    - freemail or person_exception -> identity is the full email, type=person
    - system_domains               -> identity is the domain, type=system
    - everything else              -> identity is the domain, type=organisation
    """
    email, domain = parse_sender(raw_sender)
    display_name = raw_sender.split('<')[0].strip().strip('"') or email

    if email in entity_config.get("person_emails", []):
        return email, "person", display_name, domain
    if domain in entity_config.get("freemail_domains", []):
        return email, "person", display_name, domain
    if domain in entity_config.get("system_domains", []):
        return domain, "system", display_name, domain
    return domain, "organisation", display_name, domain


class SignalStore:
    def __init__(self, entity_config: dict):
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            raise ValueError("Missing GOOGLE_CLOUD_PROJECT")
        self.db = firestore.Client(project=project_id)
        self.entity_config = entity_config

    # ---------- idempotency ----------
    def already_processed(self, message_id: str) -> bool:
        return self.db.collection("signals").document(message_id).get().exists

    # ---------- signals ----------
    def _base_signal(self, email: dict, week: str, entity_id: str) -> dict:
        return {
            "source": "gmail",
            "type": "email",
            "week": week,
            "sender_ref": entity_id,
            "sender_raw": email["sender"],
            "subject": email["subject"],
            "snippet": email["snippet"],
            "received_at": email.get("received_at"),  # added in Session 2
            "updated_at": firestore.SERVER_TIMESTAMP,
        }

    def write_junk(self, email: dict, reason: str, week: str, dry_run=False) -> str:
        entity_id, *_ = self._touch_entity(email, dry_run)
        doc = self._base_signal(email, week, entity_id)
        doc.update({"status": "junk_filtered", "filter_reason": reason})
        self._upsert_signal(email["id"], doc, dry_run)
        return entity_id

    def write_survivor(self, email: dict, week: str, dry_run=False) -> str:
        entity_id, *_ = self._touch_entity(email, dry_run)
        doc = self._base_signal(email, week, entity_id)
        doc.update({"status": "pending_classification", "filter_reason": None})
        self._upsert_signal(email["id"], doc, dry_run)
        return entity_id

    def _upsert_signal(self, message_id: str, doc: dict, dry_run: bool):
        if dry_run:
            print(f"  [DRY-RUN] signal {message_id}: {doc['status']} <- {doc['subject'][:40]}")
            return
        ref = self.db.collection("signals").document(message_id)
        if not ref.get().exists:
            doc["created_at"] = firestore.SERVER_TIMESTAMP
        ref.set(doc, merge=True)   # re-runs update, never duplicate

    # ---------- entities ----------
    def _touch_entity(self, email: dict, dry_run: bool):
        entity_id, etype, display_name, domain = resolve_entity(
            email["sender"], self.entity_config
        )
        if dry_run:
            return entity_id, etype, display_name, domain
        ref = self.db.collection("entities").document(entity_id)
        snap = ref.get()
        if snap.exists:
            ref.update({
                "last_seen": firestore.SERVER_TIMESTAMP,
                "signal_count": firestore.Increment(1),
            })
        else:
            ref.set({
                "type": etype,
                "display_name": display_name,
                "domain": domain,
                "override": False,
                "first_seen": firestore.SERVER_TIMESTAMP,
                "last_seen": firestore.SERVER_TIMESTAMP,
                "signal_count": 1,
            })
        return entity_id, etype, display_name, domain

    # ---------- runs ----------
    def write_run(self, week: str, stats: dict, dry_run=False):
        if dry_run:
            print(f"  [DRY-RUN] run for {week}: {stats}")
            return
        self.db.collection("runs").add({
            "week": week,
            **stats,
            "started_at": firestore.SERVER_TIMESTAMP,
        })
    def get_pending(self, limit: int = 50):
        """Survivors waiting for the brain."""
        q = (self.db.collection("signals")
             .where("status", "==", "pending_classification")
             .limit(limit))
        return [(d.id, d.to_dict()) for d in q.stream()]

    def save_classification(self, message_id: str, classification: dict, new_status: str):
        tokens = classification.pop("_tokens", 0)
        self.db.collection("signals").document(message_id).set(
            {"classification": classification, "status": new_status,
             "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )
        return tokens

    # ---------- dashboard reads ----------
    def get_signal(self, message_id: str) -> dict | None:
        """Single signal by Gmail message_id, or None if it was never ingested."""
        snap = self.db.collection("signals").document(message_id).get()
        return snap.to_dict() if snap.exists else None

    def get_by_status(self, status: str, limit: int = 25,
                      start_after_id: str | None = None) -> list[tuple[str, dict]]:
        """Paginated browse by status, ordered by document id (the Gmail message_id).

        The cursor is the last message_id from the previous page. Ordering by
        ``__name__`` keeps pagination stable and index-free: the automatic
        single-field index on ``status`` already sorts by document name, so an
        equality filter + order-by-__name__ needs no composite index.
        """
        q = (self.db.collection("signals")
             .where(filter=FieldFilter("status", "==", status))
             .order_by("__name__")
             .limit(limit))
        if start_after_id:
            last = self.db.collection("signals").document(start_after_id).get()
            if last.exists:
                q = q.start_after(last)
        return [(d.id, d.to_dict()) for d in q.stream()]

    def get_status_counts(self) -> dict[str, int]:
        """Count signals grouped by status via Firestore's count() aggregation
        (server-side; does not read the documents)."""
        counts: dict[str, int] = {}
        for status in ("junk_filtered", "pending_classification",
                       "classified", "needs_review", "corrected"):
            agg = (self.db.collection("signals")
                   .where(filter=FieldFilter("status", "==", status))
                   .count()
                   .get())
            counts[status] = int(agg[0][0].value)
        return counts

    def corrections_count(self) -> int:
        """Total number of correction_log documents, via count() aggregation
        (server-side; does not read the documents)."""
        agg = self.db.collection("correction_log").count().get()
        return int(agg[0][0].value)

    def category_counts(self, top: int = 10) -> list[tuple[str, int]]:
        """Top ``top`` categories by signal count among classified/corrected
        signals, as ``[(name, count), ...]`` ordered descending.

        Firestore has no GROUP BY and the category set is open-ended (the
        classifier may coin new categories), so a per-value count() is not an
        option. Instead we project *only* ``classification.category`` with
        ``select()`` — each read returns one field, not the whole signal — and
        tally in memory. Reads are bounded by the number of classified/corrected
        signals (a subset of the corpus), not the full ~9k collection.
        """
        counter: Counter[str] = Counter()
        for status in ("classified", "corrected"):
            q = (self.db.collection("signals")
                 .where(filter=FieldFilter("status", "==", status))
                 .select(["classification.category"]))
            for d in q.stream():
                cat = ((d.to_dict() or {}).get("classification") or {}).get("category")
                if cat:
                    counter[cat] += 1
        return counter.most_common(top)

    # ---------- runs ----------
    def weekly_runs(self) -> list[dict]:
        """Per-week pipeline series from the ``runs`` collection, ascending by
        week, for the dashboard trend chart.

        The collection is small (≈one doc per processed week), so a full stream
        is cheap. If a week has more than one run doc (a re-run), the most recent
        (by ``started_at``) wins so a week is never double-counted. ISO week
        labels ("YYYY-Www") sort lexicographically in chronological order.
        """
        latest: dict[str, tuple[datetime, dict]] = {}
        for d in self.db.collection("runs").stream():
            doc = d.to_dict() or {}
            week = doc.get("week")
            if not week:
                continue
            ts = doc.get("started_at") or _EPOCH
            if week not in latest or ts > latest[week][0]:
                latest[week] = (ts, doc)
        out: list[dict] = []
        for week in sorted(latest):
            doc = latest[week][1]
            out.append({
                "week": week,
                "fetched": int(doc.get("fetched", 0) or 0),
                "junk_filtered": int(doc.get("junk_filtered", 0) or 0),
                "classified": int(doc.get("classified", 0) or 0),
                "needs_review": int(doc.get("needs_review", 0) or 0),
            })
        return out

    def last_run(self) -> dict | None:
        """Most recent ``runs`` document by ``started_at``, or None if no runs
        have been recorded yet."""
        snaps = list(self.db.collection("runs")
                     .order_by("started_at", direction=firestore.Query.DESCENDING)
                     .limit(1).stream())
        return snaps[0].to_dict() if snaps else None

    # ---------- correction_log (the most valuable data in the system) ----------
    @staticmethod
    def _correction_doc(signal_ref: str, field: str, ai_value, your_value,
                        sender_ref: str | None, subject_hint: str,
                        prompt_version: str) -> dict:
        """The canonical correction_log document shape. One per changed field."""
        return {
            "signal_ref": signal_ref,
            "field": field,
            "ai_value": ai_value,
            "your_value": your_value,
            "sender_ref": sender_ref,
            "subject_hint": subject_hint,
            "prompt_version": prompt_version,
            "created_at": firestore.SERVER_TIMESTAMP,
        }

    def write_correction(self, signal_ref: str, field: str, ai_value, your_value,
                         sender_ref: str | None = None, subject_hint: str = "",
                         prompt_version: str = "v1") -> None:
        """Append one correction_log document (one per changed field)."""
        self.db.collection("correction_log").add(
            self._correction_doc(signal_ref, field, ai_value, your_value,
                                  sender_ref, subject_hint, prompt_version))

    def get_recent_corrections(self, sender_ref: str, limit: int) -> list[dict]:
        """CORRECTOR read-side source. Sender-specific corrections first (newest
        first), then recent global corrections, de-duplicated and capped at ``limit``.

        Sender-specific rows are sorted in memory to avoid a (sender_ref, created_at)
        composite index; the global fill uses the automatic created_at index.
        """
        col = self.db.collection("correction_log")
        out: list[dict] = []
        seen: set[str] = set()

        if sender_ref:
            snaps = list(col.where(filter=FieldFilter("sender_ref", "==", sender_ref))
                         .limit(limit).stream())
            snaps.sort(key=lambda s: s.to_dict().get("created_at") or _EPOCH, reverse=True)
            for s in snaps:
                out.append(s.to_dict())
                seen.add(s.id)
                if len(out) >= limit:
                    return out

        for s in (col.order_by("created_at", direction=firestore.Query.DESCENDING)
                  .limit(limit).stream()):
            if s.id in seen:
                continue
            out.append(s.to_dict())
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _field_changed(field: str, old, new) -> bool:
        """topics is a set-style list (order-insensitive); everything else is scalar."""
        if field == "topics":
            return sorted(old or []) != sorted(new or [])
        return old != new

    def apply_correction(self, message_id: str, changes: dict,
                         current_classification: dict | None = None) -> dict:
        """Atomic human correction. In a single Firestore batch:

          1. update signals/{id}.classification with the changed fields and set
             status='corrected';
          2. write one correction_log document per *actually changed* field;
          3. if sender_type changed, set the entity's type + override=True.

        Diffs ``changes`` against ``current_classification`` (falling back to the
        stored classification) so unchanged fields never log a spurious correction.
        Reclassifying a junk_filtered item works too: its baseline is empty, so the
        new category logs against ai_value=None — the firewall-was-wrong signal.

        Returns ``{"changed_fields": [...], "corrections_written": n}``.
        """
        snap = self.db.collection("signals").document(message_id).get()
        if not snap.exists:
            raise ValueError(f"signal {message_id} not found")
        sig = snap.to_dict()
        baseline = current_classification or sig.get("classification") or {}
        sender_ref = sig.get("sender_ref")
        subject_hint = sig.get("subject", "")
        prompt_version = baseline.get("prompt_version", "v1")

        # 1) diff -> only the correctable fields that actually changed
        changed: dict = {}
        for field in CORRECTABLE_FIELDS:
            if field not in changes:
                continue
            old_val, new_val = baseline.get(field), changes[field]
            if self._field_changed(field, old_val, new_val):
                changed[field] = (old_val, new_val)

        if not changed:
            return {"changed_fields": [], "corrections_written": 0}

        batch = self.db.batch()

        # 2) signal classification update + status flip
        new_classification = {**baseline}
        for field, (_old, new_val) in changed.items():
            new_classification[field] = new_val
        batch.set(
            self.db.collection("signals").document(message_id),
            {"classification": new_classification, "status": "corrected",
             "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

        # 3) one correction_log doc per changed field (auto-id)
        for field, (old_val, new_val) in changed.items():
            batch.set(
                self.db.collection("correction_log").document(),
                self._correction_doc(message_id, field, old_val, new_val,
                                     sender_ref, subject_hint, prompt_version),
            )

        # 4) entity override when a human reclassifies sender_type
        if "sender_type" in changed and sender_ref:
            batch.set(
                self.db.collection("entities").document(sender_ref),
                {"type": changed["sender_type"][1], "override": True},
                merge=True,
            )

        batch.commit()
        return {"changed_fields": list(changed.keys()),
                "corrections_written": len(changed)}

