"""Authorize one Google account locally. Keep client credentials and token private."""
import argparse
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-secrets", default="client_secret.json")
    parser.add_argument("--token-file", default="token.json")
    args = parser.parse_args()
    path = Path(args.token_file)
    if path.exists():
        raise SystemExit("Token file already exists. Back it up or remove it manually before reauthorizing.")
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secrets, SCOPES)
    credentials = flow.run_local_server(host="localhost", bind_addr="127.0.0.1", port=0, access_type="offline", prompt="consent")
    if not credentials.refresh_token:
        raise SystemExit("Google did not return a refresh token. No file was written. Revoke access and retry.")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(credentials.to_json())
    print(f"Saved private Google credentials to {path}. Do not commit or share this file.")

if __name__ == "__main__": main()
