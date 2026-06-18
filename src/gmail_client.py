import base64
from googleapiclient.discovery import build
from datetime import datetime, timezone



class GmailClient:
    def __init__(self, credentials):
        self.service = build('gmail', 'v1', credentials=credentials)

    def get_body_excerpt(self, message_id: str, max_chars: int = 1500) -> str:
        """Fetch and flatten an email body to plain text, truncated. Survivors only."""
        msg = self.service.users().messages().get(
            userId='me', id=message_id, format='full'
        ).execute()
        text = self._extract_text(msg.get('payload', {}))
        text = ' '.join(text.split())          # collapse whitespace/newlines
        return text[:max_chars]

    def _extract_text(self, payload) -> str:
        """Walk the MIME tree, prefer text/plain, fall back to stripped text/html."""
        mime = payload.get('mimeType', '')
        body = payload.get('body', {})
        data = body.get('data')

        if mime == 'text/plain' and data:
            return self._decode(data)
        if mime == 'text/html' and data:
            return self._strip_html(self._decode(data))

        # multipart: recurse, prefer the first text/plain we find
        parts = payload.get('parts', [])
        plain = [self._extract_text(p) for p in parts if p.get('mimeType') == 'text/plain']
        if any(plain):
            return ' '.join(t for t in plain if t)
        return ' '.join(self._extract_text(p) for p in parts)  # fall back to everything

    @staticmethod
    def _decode(data: str) -> str:
        return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')

    @staticmethod
    def _strip_html(html: str) -> str:
        import re
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
        return re.sub(r'<[^>]+>', ' ', html)
    #tool is not deliting any mail it is only labeling it with propper label
    def apply_label(self, message_id: str, label_name: str):
        """Create the label if missing, then add it to the message. Add-only."""
        label_id = self._ensure_label(label_name)
        self.service.users().messages().modify(
            userId='me', id=message_id, body={'addLabelIds': [label_id]}
        ).execute()

    def _ensure_label(self, label_name: str) -> str:
        existing = self.service.users().labels().list(userId='me').execute().get('labels', [])
        for lab in existing:
            if lab['name'] == label_name:
                return lab['id']
        created = self.service.users().labels().create(
            userId='me', body={'name': label_name,
                                'labelListVisibility': 'labelShow',
                                'messageListVisibility': 'show'}
        ).execute()
        return created['id']
    def fetch_batch_by_date(self, start_date, end_date, limit=50):
        """Fetches emails strictly within a specific time window."""
        
        # We construct a highly specific Gmail Search Query
        # e.g., "after:2024/01/01 before:2024/01/08 -in:chats"
        start_formatted = start_date.replace("-", "/")
        end_formatted = end_date.replace("-", "/")
        query = f"after:{start_formatted} before:{end_formatted} -in:chats"
        
        results = self.service.users().messages().list(userId='me', q=query, maxResults=limit).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return []

        parsed_emails = []
        for msg in messages:
            msg_data = self.service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            
            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
            internal_ms = int(msg_data.get('internalDate', 0))
            received_at = datetime.fromtimestamp(internal_ms / 1000, tz=timezone.utc)
            
            parsed_emails.append({
                "id": msg['id'],
                "subject": subject,
                "sender": sender,
                "snippet": msg_data.get('snippet', ''),
                "received_at": received_at,
            })

            
        return parsed_emails