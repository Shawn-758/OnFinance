from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any

from app.config import get_settings


def send_email(email: dict[str, str]) -> dict[str, Any]:
    """email through SMTP or print it for a zero-configuration demo."""
    settings = get_settings()
    backend = settings.email_backend.strip().lower()
    if backend == "console":
        print(f"Demo email to {email['to']}\nSubject: {email['subject']}\n\n{email['body']}")
        return {"status": "simulated", "backend": "console"}
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
