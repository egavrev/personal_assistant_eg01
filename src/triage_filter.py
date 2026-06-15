import re


class TriageFilter:
    def __init__(self, filter_config: dict):
        """
        filter_config is the `triage_filter` section of config.yaml:
          { "junk_senders": [...], "junk_subjects": [...] }
        Subject patterns are compiled once here, not on every email.
        """
        self.junk_senders = [s.lower() for s in filter_config.get("junk_senders", [])]
        self.junk_subjects = [
            re.compile(p, re.IGNORECASE) for p in filter_config.get("junk_subjects", [])
        ]

    def evaluate(self, email_data):
        """
        Returns (is_valuable: bool, reason: str).
        False -> dropped as junk (Phase 1). True -> survives to the AI layer.
        """
        sender_lower = email_data["sender"].lower()
        subject = email_data["subject"]

        for junk_sender in self.junk_senders:
            if junk_sender in sender_lower:
                return False, f"Automated sender: {junk_sender}"

        for pattern in self.junk_subjects:
            if pattern.search(subject):
                return False, f"Transactional subject: {pattern.pattern}"

        return True, "Passed heuristics"