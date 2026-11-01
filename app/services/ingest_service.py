from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import ROOT_DIR, get_settings
from app.document_checklist import build_checklist, build_missing_documents_email
from app.mailer import create_email_draft
from app.tracker import sync_client
from app.db.models import Client, Document, IngestionJob
from app.db.session import SessionLocal
from app.extractors.email_parser import parse_email_text, split_sample_emails
from app.extractors.field_extractor import merge_fields
from app.extractors.image_ocr import extract_image
from app.extractors.pdf_parser import extract_pdf
from app.validate_data import validate_fields


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
PDF_SUFFIXES = {".pdf"}


def queue_job(
    db: Session,
    *,
    source_type: str,
    raw_text: str | None = None,
    source_ref: str | None = None,
) -> IngestionJob:
    job = IngestionJob(
        source_type=source_type,
        status="received",
        raw_text=raw_text,
        source_ref=source_ref,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def process_ingestion_job(
    job_id: int,
    saved_files: list[str] | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Runs in FastAPI BackgroundTasks. Opens its own DB session."""
    db = SessionLocal()
    try:
        job = db.get(IngestionJob, job_id)
        if job is None:
            return
        job.status = "processing"
        db.commit()

        payloads: list[dict[str, Any]] = []
        document_results: list[dict[str, Any]] = []
        if extra_fields:
            payloads.append(extra_fields)

        email_attachments: list[str] = []
        if job.raw_text:
            parsed = parse_email_text(job.raw_text)
            payloads.append(parsed["fields"])
            email_attachments = parsed.get("attachments") or []
            initial_client = _upsert_client(db, parsed["fields"], "received")
            if initial_client:
                job.client_id = initial_client.id
            db.commit()
        elif extra_fields:
            initial_client = _upsert_client(db, extra_fields, "received")
            if initial_client:
                job.client_id = initial_client.id
            db.commit()

        for file_path in saved_files or []:
            result = _extract_file(file_path)
            payloads.append(result["fields"])
            document_results.append(result)
            _store_document(db, job, result, file_path)

        if email_attachments and not saved_files:
            pack_dir = ROOT_DIR
            for name in email_attachments:
                candidate = pack_dir / name
                if candidate.exists():
                    result = _extract_file(str(candidate))
                    payloads.append(result["fields"])
                    document_results.append(result)
                    stored = _copy_to_uploads(candidate, job.id)
                    _store_document(db, job, result, stored)

        merged = merge_fields(*payloads)
        validation_results = _validate_documents(document_results, merged)
        checklist = build_checklist(merged.get("service_needed"), document_results)
        missing_documents_email = build_missing_documents_email(
            merged.get("email"),
            merged.get("name"),
            checklist,
            validation_results,
            document_results,
        )
        email_delivery = (
            create_email_draft(missing_documents_email)
            if missing_documents_email and get_settings().email_backend.strip().lower()
            in {"console", "gmail_draft"}
            else None
        )
        invalid_documents = [
            result for result in validation_results if not result["valid"]
        ]
        documents_valid = bool(validation_results) and not invalid_documents
        has_unusable_documents = bool(checklist["unusable_documents"]) or any(
            document.get("quality_flag") in {"low_quality", "unreadable"}
            or not (document.get("text") or "").strip()
            for document in document_results
        )
        if invalid_documents:
            job_status = "correction_required"
        elif (
            has_unusable_documents
            or (not checklist["complete"] and checklist["service"])
        ):
            job_status = "docs_pending"
        else:
            job_status = "ready_for_review"
        client_status = job_status
        client = _upsert_client(db, merged, client_status)
        job.client_id = client.id if client else None
        tracker_status = _tracker_status(job_status, client is not None)
        tracker_sync = sync_client(merged, tracker_status)
        job.extracted_json = json.dumps(
            {
                "fields": merged,
                "validation": validation_results,
                "checklist": checklist,
                "missing_documents_email": missing_documents_email,
                "email_delivery": email_delivery,
                "email_approval": (
                    "pending" if missing_documents_email else "not_required"
                ),
                "tracker_sync": tracker_sync,
            },
            default=str,
        )
        job.status = job_status
        job.completed_at = datetime.now(timezone.utc)
        if client:
            for document in job.documents:
                document.client_id = client.id
        db.commit()
    except Exception as exc:  # noqa: BLE001 — persist failure on the job row
        db.rollback()
        job = db.get(IngestionJob, job_id)
        if job:
            job.status = "processing_failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()


def ingest_sample_pack(db: Session, pack_dir: str | None = None) -> list[int]:
    """Queue one job per email in sample_emails.txt. Attachments are resolved from pack_dir."""
    directory = Path(pack_dir) if pack_dir else ROOT_DIR
    emails_path = directory / "sample_emails.txt"
    blob = emails_path.read_text(encoding="utf-8")
    job_ids: list[int] = []
    for message in split_sample_emails(blob):
        job = queue_job(db, source_type="email", raw_text=message, source_ref=emails_path.name)
        job_ids.append(job.id)
    return job_ids


def _extract_file(file_path: str) -> dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return extract_image(path)
    if suffix in PDF_SUFFIXES:
        return extract_pdf(path)
    raise ValueError(f"Unsupported file type: {path.name}")


def _validate_documents(
    document_results: list[dict[str, Any]], merged_fields: dict[str, Any]
) -> list[dict[str, Any]]:
    validation_results: list[dict[str, Any]] = []
    supported_types = {"aadhaar", "pan", "gst", "electricity_bill"}
    for result in document_results:
        fields = dict(result["fields"])
        document_type = fields.get("document_type")
        if document_type not in supported_types:
            continue
        fields.update(
            {
                key: value
                for key, value in merged_fields.items()
                if value and not fields.get(key)
            }
        )
        validation = validate_fields(fields)
        validation["filename"] = result["filename"]
        validation_results.append(validation)
    return validation_results


def _copy_to_uploads(source: Path, job_id: int) -> str:
    settings = get_settings()
    dest_dir = Path(settings.upload_dir) / str(job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return str(dest)


def _store_document(db: Session, job: IngestionJob, result: dict[str, Any], stored_path: str) -> Document:
    document = Document(
        job_id=job.id,
        filename=result["filename"],
        stored_path=stored_path,
        document_type=result.get("document_type") or "unknown",
        extracted_text=result.get("text"),
        quality_flag=result.get("quality_flag") or "ok",
        blur_score=str(result.get("blur_score")) if result.get("blur_score") is not None else None,
    )
    db.add(document)
    db.flush()
    return document


def _upsert_client(
    db: Session, fields: dict[str, Any], status: str
) -> Client | None:
    if not any(fields.get(key) for key in ("email", "pan", "phone", "name")):
        return None

    client = None
    if fields.get("email"):
        client = db.query(Client).filter(Client.email == fields["email"]).one_or_none()
    if client is None and fields.get("pan"):
        client = db.query(Client).filter(Client.pan == fields["pan"]).one_or_none()

    if client is None:
        client = Client(status=status)
        db.add(client)
    else:
        client.status = status

    for key in ("name", "pan", "aadhaar", "email", "phone", "service_needed", "gstin"):
        value = fields.get(key)
        if value and not getattr(client, key):
            setattr(client, key, value)

    db.flush()
    return client


def _tracker_status(job_status: str, client_saved: bool) -> str:
    if job_status == "docs_pending":
        return "docs pending"
    if job_status == "correction_required":
        return "correction required"
    if job_status in {"processing_failed"}:
        return "processing failed"
    if job_status in {"ready_for_review", "under_review"}:
        return "ready for review"
    if job_status == "approved":
        return "approved"
    if job_status == "rejected":
        return "rejected"
    if job_status == "onboarded":
        return "onboarded"
    return "new"
