import os
import sys
import subprocess
from google_auth_oauthlib.flow import InstalledAppFlow

def main():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

    if not client_id or not client_secret or not project_id:
        print("ERROR: Missing environment variables! Make sure ID, Secret, and Project are exported.")
        sys.exit(1)

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
    
    print("\n=== STARTING ONE-TIME OAUTH FLOW ===")
    creds = flow.run_local_server(
        host='localhost',
        port=8080,
        authorization_prompt_message='Please copy and visit this URL in your browser: \n\n{url}\n',
        success_message='Authorization successful! You can close this browser tab.',
        open_browser=False
    )

    refresh_token = creds.refresh_token
    if not refresh_token:
        print("\nERROR: No Refresh Token returned.")
        print("Ensure your OAuth app is set to 'Testing' and 'External' status in GCP.")
        sys.exit(1)

    print("\n[✓] Permanent Refresh Token acquired successfully!")
    print(f"Uploading token to Secret Manager using native gcloud CLI...")

    # We use subprocess to securely pass the token directly to gcloud without saving it to a file
    command = [
        "gcloud", "secrets", "versions", "add", "gmail-refresh-token",
        "--project", project_id,
        "--data-file", "-"
    ]
    
    try:
        # input=refresh_token pipes the secret directly into standard input
        process = subprocess.run(
            command, 
            input=refresh_token.encode('utf-8'), 
            check=True, 
            capture_output=True, 
            text=True
        )
        print(f"[✓] Success! Token locked securely in Secret Manager.")
    except subprocess.CalledProcessError as e:
        print(f"\nERROR saving secret via gcloud: {e.stderr}")
        sys.exit(1)

if __name__ == "__main__":
    main()