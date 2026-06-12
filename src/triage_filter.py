import re

class TriageFilter:
    def __init__(self):
        # We define a list of keywords and patterns that scream "Automated Junk"
        self.junk_senders = [
            "no-reply", "noreply", "notifications@", "do-not-reply",
            "marketing", "promotions", "newsletter@", "info@"
        ]
        
        self.junk_subjects = [
            r"out of office",
            r"jira\]",
            r"reset your password",
            r"verify your email",
            r"security alert",
            r"meeting canceled",
            r"your receipt"
        ]

    def evaluate(self, email_data):
        """
        Returns a tuple: (is_valuable: bool, reason: str)
        If False, the email is flagged for the trash/archive.
        If True, it survives and moves to the AI layer.
        """
        sender_lower = email_data['sender'].lower()
        subject_lower = email_data['subject'].lower()

        # 1. Fast Sender Check
        for junk_sender in self.junk_senders:
            if junk_sender in sender_lower:
                return False, f"Automated sender detected: {junk_sender}"

        # 2. Regex Subject Check
        for pattern in self.junk_subjects:
            if re.search(pattern, subject_lower):
                return False, f"Transactional subject detected: {pattern}"

        # 3. If it passes all rules, it goes to the AI
        return True, "Passed heuristics"