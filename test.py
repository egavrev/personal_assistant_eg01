from src.auth import get_gmail_credentials
from src.state_manager import StateManager
from src.gmail_client import GmailClient
from src.triage_filter import TriageFilter
import yaml

print('1. Initializing Pipeline Services...')
creds = get_gmail_credentials()
gmail = GmailClient(creds)
state = StateManager()
firewall = TriageFilter()

print('2. Getting Time-Slice from Firestore...')
# We ask for a tiny 1-day slice just for this test
start_date, end_date = state.get_date_window(days_to_fetch=1)
print(f'   Targeting: {start_date} to {end_date}')

print('3. Fetching raw batch from Gmail...')
raw_emails = gmail.fetch_batch_by_date(start_date, end_date, limit=20)
print(f'   Pulled {len(raw_emails)} raw emails.')

print('\n4. Running Heuristic Firewall...')
survivors = []
for email in raw_emails:
    is_valuable, reason = firewall.evaluate(email)
    if is_valuable:
        survivors.append(email)
    else:
        print(f'[JUNK DROPPED] {email["subject"][:30]}... -> {reason}')

print(f'\n=== PIPELINE RESULTS ===')
print(f'Original Batch: {len(raw_emails)}')
print(f'Sent to Archive: {len(raw_emails) - len(survivors)}')
print(f'Surviving for AI: {len(survivors)}')