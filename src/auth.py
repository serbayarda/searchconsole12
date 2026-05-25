"""Google Search Console OAuth (desktop flow) with cached refresh token."""
from __future__ import annotations

import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

ROOT = Path(__file__).resolve().parent.parent
CLIENT_SECRET = ROOT / "client_secret.json"
TOKEN_FILE = ROOT / "token.json"


def get_credentials() -> Credentials:
    creds: Credentials | None = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
        return creds

    if not CLIENT_SECRET.exists():
        raise FileNotFoundError(
            f"Missing {CLIENT_SECRET}. Download an OAuth 2.0 Desktop client "
            "from Google Cloud Console (with Search Console API enabled) and "
            "save it as client_secret.json in the repo root."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    # port=0 picks a random free port; opens browser for consent
    creds = flow.run_local_server(port=0, open_browser=True)
    TOKEN_FILE.write_text(creds.to_json())
    # Tighten permissions on the token cache (best-effort)
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass
    return creds
