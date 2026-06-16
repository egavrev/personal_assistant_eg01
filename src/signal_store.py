import os
import re
from google.cloud import firestore


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

