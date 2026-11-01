from __future__ import annotations

import smtplib
import base64
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.config import get_settings


def create_email_draft(email: dict[str, str]) -> dict[str, Any]:
    """Create a draft for human verification configured Gmail account."""
    settings = get_settings()
    backend = settings.email_backend.strip().lower()
    if backend == "console":
        print(
            f"Demo email draft to {email['to']}\n"
            f"Subject: {email['subject']}\n\n{email['body']}"
        )
        return {"status": "drafted", "backend": "console"}
    if backend != "gmail_draft":
        return {"status": "not_requested", "backend": backend}
    if not settings.gmail_credentials_file:
        return {
            "status": "failed",
            "backend": "gmail_draft",
            "error": "GMAIL_CREDENTIALS_FILE is required",
        }

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        return {
            "status": "failed",
            "backend": "gmail_draft",
            "error": f"Gmail API dependencies are missing: {exc}",
        }

    token_path = Path(settings.gmail_token_file)
    credentials = None
    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(
            str(token_path), ["https://www.googleapis.com/auth/gmail.compose"]
        )
    try:
        if credentials is None or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                from google.auth.transport.requests import Request

                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    settings.gmail_credentials_file,
                    ["https://www.googleapis.com/auth/gmail.compose"],
                )
                credentials = flow.run_local_server(port=0)
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(credentials.to_json(), encoding="utf-8")

        message = EmailMessage()
        message["To"] = email["to"]
        message["Subject"] = email["subject"]
        message.set_content(email["body"])
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        draft = (
            build("gmail", "v1", credentials=credentials)
            .users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw_message}})
            .execute()
        )
    except (OSError, ValueError, HttpError) as exc:
        return {"status": "failed", "backend": "gmail_draft", "error": str(exc)}
    return {
        "status": "drafted",
        "backend": "gmail_draft",
        "draft_id": draft.get("id"),
        "message_id": draft.get("message", {}).get("id"),
    }


def send_email(email: dict[str, str]) -> dict[str, Any]:
    """email through SMTP or print it for a zero-configuration demo."""
    settings = get_settings()
    backend = settings.email_backend.strip().lower()
    if backend == "console":
        print(f"Demo email to {email['to']}\nSubject: {email['subject']}\n\n{email['body']}")
        return {"status": "simulated", "backend": "console"}
    if backend == "gmail_draft":
        return {
            "status": "not_sent",
            "backend": "gmail_draft",
            "error": "This backend creates drafts during ingestion; send the draft manually in Gmail",
        }
    if backend != "smtp":
        return {"status": "not_sent", "backend": backend, "error": "Unsupported email backend"}
    if not settings.smtp_host or not settings.smtp_from_email:
        return {
            "status": "not_sent",
            "backend": "smtp",
            "error": "SMTP_HOST and SMTP_FROM_EMAIL are required",
        }

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = email["to"]
    message["Subject"] = email["subject"]
    message.set_content(email["body"])
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        return {"status": "failed", "backend": "smtp", "error": str(exc)}
    return {"status": "sent", "backend": "smtp"}
