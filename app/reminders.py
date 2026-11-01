from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import IngestionJob
from app.mailer import send_email


UNRESOLVED_STATUSES = {"docs_pending", "correction_required"}


def send_due_reminders(db: Session) -> list[dict[str, Any]]:
    """Send one follow-up for unresolved jobs older than the configured delay."""
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.reminder_after_days)
    results: list[dict[str, Any]] = []

    jobs = (
        db.query(IngestionJob)
        .filter(IngestionJob.status.in_(UNRESOLVED_STATUSES))
        .all()
    )
    for job in jobs:
        created_at = job.created_at
        if created_at is None:
            continue
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        if created_at > cutoff:
            continue

        payload = json.loads(job.extracted_json or "{}")
        if payload.get("reminder_sent_at"):
            continue
        if payload.get("email_approval") != "approved":
            continue
        email = payload.get("missing_documents_email")
        if not email:
            continue

        reminder = dict(email)
        reminder["subject"] = f"Reminder: {email['subject']}"
        delivery = send_email(reminder)
        result = {
            "job_id": job.id,
            "recipient": reminder["to"],
            "delivery": delivery,
        }
        if delivery.get("status") in {"sent", "simulated"}:
            payload["reminder_sent_at"] = datetime.now(timezone.utc).isoformat()
            payload["reminder_delivery"] = delivery
            job.extracted_json = json.dumps(payload, default=str)
            db.commit()
        results.append(result)
    return results
