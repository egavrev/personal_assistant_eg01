from googleapiclient.discovery import build
from datetime import datetime, timezone


class GmailClient:
    def __init__(self, credentials):
        self.service = build('gmail', 'v1', credentials=credentials)

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