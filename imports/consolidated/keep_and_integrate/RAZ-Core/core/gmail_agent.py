"""
RAZ Core - Gmail Agent
Provides unread summary and send actions.
"""

import os
import base64
from email.mime.text import MIMEText

from system.config_loader import load_config

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_paths() -> tuple[str, str]:
    cfg = load_config()
    creds = cfg.get("google_credentials_path") or os.path.join(BASE_DIR, "system", "google_credentials.json")
    token = cfg.get("google_token_path") or os.path.join(BASE_DIR, "system", "google_token.json")
    return creds, token


def _get_service(scopes: list[str]):
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except Exception:
        return None, (
            "RAZ: Google API libraries are not installed.\n"
            "Install in your venv: pip install google-api-python-client google-auth-oauthlib google-auth-httplib2"
        )

    creds_path, token_path = _get_paths()
    creds = None

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, scopes)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not os.path.exists(creds_path):
                return None, (
                    f"RAZ: Missing Google credentials file.\n"
                    f"Expected: {creds_path}\n"
                    "Create OAuth Desktop credentials in Google Cloud and place the JSON there."
                )
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        return service, ""
    except Exception as e:
        return None, f"RAZ: Gmail client init failed: {e}"


def get_unread_summary(max_results: int = 8) -> str:
    scopes = ["https://www.googleapis.com/auth/gmail.readonly"]
    service, err = _get_service(scopes)
    if not service:
        return err

    try:
        result = (
            service.users()
            .messages()
            .list(userId="me", q="is:unread", maxResults=max_results)
            .execute()
        )
        msgs = result.get("messages", [])
    except Exception as e:
        return f"RAZ: Could not read Gmail: {e}"

    if not msgs:
        return "RAZ: No unread Gmail messages."

    lines = [f"RAZ: Gmail unread ({len(msgs)}):"]
    for m in msgs:
        try:
            detail = service.users().messages().get(userId="me", id=m["id"], format="metadata", metadataHeaders=["From", "Subject", "Date"]).execute()
            headers = {h.get("name", ""): h.get("value", "") for h in detail.get("payload", {}).get("headers", [])}
            sender = headers.get("From", "(unknown sender)")
            subject = headers.get("Subject", "(no subject)")
            date = headers.get("Date", "")
            lines.append(f"  From: {sender}")
            lines.append(f"  Subj: {subject}")
            lines.append(f"  Date: {date}")
            lines.append("  ---")
        except Exception:
            continue
    return "\n".join(lines)


def send_gmail(to_addr: str, subject: str, body: str) -> str:
    scopes = ["https://www.googleapis.com/auth/gmail.send"]
    service, err = _get_service(scopes)
    if not service:
        return err

    try:
        msg = MIMEText(body)
        msg["to"] = to_addr
        msg["subject"] = subject
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"RAZ: Gmail sent to {to_addr}. Message id: {sent.get('id', '(unknown)')}"
    except Exception as e:
        return f"RAZ: Gmail send failed: {e}"
