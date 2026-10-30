from typing import Any

from pydantic import BaseModel, Field


class EmailIngestRequest(BaseModel):
    raw_email: str = Field(..., description="Full email text, including headers if available")
    source_ref: str | None = Field(default=None, description="Optional mailbox id or filename")


class SamplePackIngestRequest(BaseModel):
    emails_path: str | None = None
    pack_dir: str | None = None


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    source_type: str
    client_id: int | None = None
    extracted: dict[str, Any] | None = None
    error_message: str | None = None


class ClientResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    name: str | None
    pan: str | None
    aadhaar: str | None
    email: str | None
    phone: str | None
    service_needed: str | None
    gstin: str | None
    status: str
