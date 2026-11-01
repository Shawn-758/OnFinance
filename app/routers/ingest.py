from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import IngestionJob
from app.db.session import get_db
from app.schemas.ingest import EmailIngestRequest, JobStatusResponse, SamplePackIngestRequest
from app.services.ingest_service import ingest_sample_pack, process_ingestion_job, queue_job
from app.reminders import send_due_reminders
from app.mailer import send_email


router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/email", response_model=JobStatusResponse)
def ingest_email(
    payload: EmailIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = queue_job(db, source_type="email", raw_text=payload.raw_email, source_ref=payload.source_ref)
    background_tasks.add_task(process_ingestion_job, job.id)
    return JobStatusResponse(job_id=job.id, status=job.status, source_type=job.source_type)


@router.post("/documents", response_model=JobStatusResponse)
async def ingest_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    email: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    job = queue_job(db, source_type="documents", raw_text=email, source_ref="upload")
    saved = await _save_uploads(job.id, files)
    extra = {"email": email} if email else None
    background_tasks.add_task(process_ingestion_job, job.id, saved, extra)
    return JobStatusResponse(job_id=job.id, status=job.status, source_type=job.source_type)


@router.post("/sample-pack", response_model=list[JobStatusResponse])
def ingest_sample_pack_route(
    payload: SamplePackIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> list[JobStatusResponse]:
    job_ids = ingest_sample_pack(db, payload.pack_dir)
    responses: list[JobStatusResponse] = []
    for job_id in job_ids:
        job = db.get(IngestionJob, job_id)
        background_tasks.add_task(process_ingestion_job, job_id)
        responses.append(
            JobStatusResponse(job_id=job_id, status=job.status, source_type=job.source_type)
        )
    return responses


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    extracted = json.loads(job.extracted_json) if job.extracted_json else None
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        source_type=job.source_type,
        client_id=job.client_id,
        extracted=extracted,
        error_message=job.error_message,
    )


@router.post("/reminders/run")
def run_reminders(db: Session = Depends(get_db)) -> dict[str, object]:
    """Send one two-day follow-up for each still-unresolved ingestion job."""
    results = send_due_reminders(db)
    return {"sent": len(results), "results": results}


@router.post("/jobs/{job_id}/approve-email")
def approve_email(job_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    job = db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    payload = json.loads(job.extracted_json or "{}")
    email = payload.get("missing_documents_email")
    if not email:
        raise HTTPException(status_code=400, detail="No email draft requires approval")
    if payload.get("email_approval") == "approved":
        raise HTTPException(status_code=409, detail="Email already approved")
    email_delivery = payload.get("email_delivery") or {}
    if email_delivery.get("backend") == "gmail_draft":
        return {
            "job_id": job.id,
            "email_approval": "manual_in_gmail",
            "delivery": email_delivery,
            "message": "Draft created in Gmail. Review and send it manually from Gmail.",
        }

    delivery = send_email(email)
    if delivery.get("status") not in {"sent", "simulated"}:
        raise HTTPException(status_code=502, detail={"delivery": delivery})
    payload["email_approval"] = "approved"
    payload["email_delivery"] = delivery
    job.extracted_json = json.dumps(payload, default=str)
    db.commit()
    return {"job_id": job.id, "email_approval": payload["email_approval"], "delivery": delivery}


async def _save_uploads(job_id: int, files: list[UploadFile]) -> list[str]:
    settings = get_settings()
    dest_dir = Path(settings.upload_dir) / str(job_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for upload in files:
        dest = dest_dir / (upload.filename or "unnamed")
        with dest.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        saved.append(str(dest))
    return saved
