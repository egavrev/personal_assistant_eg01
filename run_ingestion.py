import yaml
from src.auth import get_gmail_credentials
from src.state_manager import StateManager
from src.gmail_client import GmailClient
from src.triage_filter import TriageFilter

def main():
    # 1. Load System Configuration
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    
    days_to_fetch = config["ingestion"]["days_per_batch"]

    print('🚀 Initializing Ingestion Pipeline...')
    creds = get_gmail_credentials()
    gmail = GmailClient(creds)
    state = StateManager()
    firewall = TriageFilter()

    # 2. Ask Firestore where we left off
    start_date, end_date = state.get_date_window(days_to_fetch=days_to_fetch)
    print(f'\n📅 Processing Window: {start_date} to {end_date}')

    # 3. Fetch that specific slice from Gmail
    print('📥 Fetching historical batch from Gmail...')
    # We increase the limit to 500 to ensure we capture a full week of history
    raw_emails = gmail.fetch_batch_by_date(start_date, end_date, limit=500) 
    
    if not raw_emails:
        print("   No emails found in this timeframe.")
    else:
        print(f'   Pulled {len(raw_emails)} raw emails.')

        # 4. Run the Free Firewall
        print('🛡️ Running Heuristic Firewall...')
        survivors = []
        for email in raw_emails:
            is_valuable, reason = firewall.evaluate(email)
            if is_valuable:
                survivors.append(email)

        print(f'\n=== PIPELINE RESULTS ===')
        print(f'Original Batch: {len(raw_emails)}')
        print(f'Sent to Archive (Free Filter): {len(raw_emails) - len(survivors)}')
        print(f'Surviving for AI: {len(survivors)}')

    # 5. Move the Bookmark Forward!
    print(f'\n⏭️ Advancing database cursor to {end_date}...')
    state.advance_cursor(end_date)
    print("✅ Run complete. Run the script again to process the next week.")

if __name__ == "__main__":
    main()