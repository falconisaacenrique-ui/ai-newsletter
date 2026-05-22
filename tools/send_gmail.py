"""Send the rendered HTML email to subscribers via the Gmail API.

Two auth shapes are supported:
  - Local dev: credentials.json + token.json files in the project root.
  - GitHub Actions: GMAIL_CREDENTIALS_JSON and GMAIL_TOKEN_JSON env vars
    holding the file contents as JSON strings.

First-time auth (local only):
    python tools/send_gmail.py --auth
which mints token.json by opening a browser. You then upload token.json's
contents to the GMAIL_TOKEN_JSON GitHub secret.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, env, log, read_json

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def _load_creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    token_env = os.environ.get("GMAIL_TOKEN_JSON", "").strip()
    creds_env = os.environ.get("GMAIL_CREDENTIALS_JSON", "").strip()
    token_path = ROOT / "token.json"
    creds_path = ROOT / "credentials.json"

    if token_env:
        creds = Credentials.from_authorized_user_info(json.loads(token_env), SCOPES)
    elif token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    else:
        return None

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # If we loaded from file, persist the refreshed token.
        if token_path.exists() and not token_env:
            token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _auth_flow_local() -> None:
    """Mint token.json by running the local OAuth installed-app flow."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    creds_path = ROOT / "credentials.json"
    token_path = ROOT / "token.json"
    if not creds_path.exists():
        sys.exit(f"credentials.json missing at {creds_path}. Download "
                 "an OAuth client (Desktop) from Google Cloud Console.")
    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"✓ token.json written to {token_path}")
    print("Upload the contents of token.json to the GMAIL_TOKEN_JSON GitHub secret.")


def _gmail_service():
    from googleapiclient.discovery import build
    creds = _load_creds()
    if creds is None:
        sys.exit("No Gmail credentials. Run: python tools/send_gmail.py --auth")
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _build_message(to_addr: str, subject: str, html: str,
                   from_addr: str, from_name: str) -> dict:
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["From"] = f"{from_name} <{from_addr}>" if from_name else from_addr
    msg["Subject"] = subject
    msg.set_content("This email is best viewed in HTML. "
                    "If you can read this, your client suppressed HTML.")
    msg.add_alternative(html, subtype="html")
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    return {"raw": raw}


def send(html: str, subject: str, recipients: list[dict],
         dry_run: bool = False, to_self: bool = False) -> None:
    from_addr = env("NEWSLETTER_FROM")
    from_name = env("NEWSLETTER_FROM_NAME", required=False, default="AI Daily")

    if to_self:
        recipients = [{"email": from_addr, "name": "self",
                       "lang_pref": "en", "active": True}]

    if dry_run:
        log.info(f"[dry-run] would send to "
                 f"{[r['email'] for r in recipients if r.get('active', True)]}")
        return

    svc = _gmail_service()
    for r in recipients:
        if not r.get("active", True):
            continue
        to = r["email"]
        try:
            msg = _build_message(to, subject, html, from_addr, from_name)
            svc.users().messages().send(userId="me", body=msg).execute()
            log.info(f"sent → {to}")
        except Exception as e:
            log.error(f"send failed for {to}: {e}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--auth", action="store_true",
                    help="One-time local OAuth flow to mint token.json")
    ap.add_argument("--html", help="path to rendered HTML")
    ap.add_argument("--subject", default="AI Daily")
    ap.add_argument("--subscribers", help="subscribers.json")
    ap.add_argument("--to-self", action="store_true",
                    help="send only to NEWSLETTER_FROM address")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.auth:
        _auth_flow_local()
        return

    if not args.html:
        sys.exit("--html required (unless --auth)")
    html = Path(args.html).read_text(encoding="utf-8")
    recipients = []
    if args.subscribers and Path(args.subscribers).exists():
        recipients = read_json(Path(args.subscribers)).get("subscribers", [])
    send(html, args.subject, recipients,
         dry_run=args.dry_run, to_self=args.to_self)


if __name__ == "__main__":
    main()
