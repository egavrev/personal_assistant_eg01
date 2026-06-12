import os
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("ERROR: Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET environment variables.")
        sys.exit(1)

    # We need the Gmail modify scope to read and manage labels
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080"]
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    
    print("\n=== STARTING OAUTH FLOW ===")
    creds = flow.run_local_server(
        host='localhost',
        port=8080,
        authorization_prompt_message='Please click the link below to authorize:\n\n{url}\n',
        success_message='Authorization successful! You can close this tab.',
        open_browser=False
    )

    if creds.refresh_token:
        print("\n\n👇👇👇 YOUR REFRESH TOKEN (COPY THIS EXACTLY) 👇👇👇")
        print(f"\n{creds.refresh_token}\n")
        print("👆👆👆 ========================================= 👆👆👆\n\n")
    else:
        print("\n❌ Google did not return a Refresh Token.")
        print("This usually happens if you already granted permission recently.")
        print("Go to https://myaccount.google.com/connections, remove 'Personal AI POC', and run this script again.")

if __name__ == "__main__":
    main()