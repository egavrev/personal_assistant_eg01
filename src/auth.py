import os
import subprocess
from google.oauth2.credentials import Credentials

def get_gmail_credentials():
    # 1. Pull the environment variables
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not all([project_id, client_id, client_secret]):
        raise ValueError("Missing GOOGLE_CLOUD_PROJECT, GOOGLE_CLIENT_ID, or GOOGLE_CLIENT_SECRET environment variables.")

    # 2. Reach into Secret Manager using the native gcloud CLI bypass
    command = [
        "gcloud", "secrets", "versions", "access", "latest",
        "--secret", "gmail-refresh-token",
        "--project", project_id
    ]
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        refresh_token = result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to fetch token from Secret Manager: {e.stderr}")

    # 3. Use the refresh token to silently generate a fresh session key
    creds = Credentials(
        token=None, 
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    return creds