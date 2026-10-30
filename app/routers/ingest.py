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
