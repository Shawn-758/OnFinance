from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Client, Document
from app.db.session import get_db
from app.schemas.ingest import ClientResponse
from app.tracker import sync_client


router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=list[ClientResponse])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    return db.query(Client).order_by(Client.id.desc()).all()


@router.get("/{client_id}")
def get_client(client_id: int, db: Session = Depends(get_db)) -> dict:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    documents = db.query(Document).filter(Document.client_id == client.id).all()
    return {
        "id": client.id,
        "name": client.name,
        "pan": client.pan,
        "aadhaar": client.aadhaar,
        "email": client.email,
        "phone": client.phone,
        "service_needed": client.service_needed,
        "gstin": client.gstin,
        "status": client.status,
        "documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "document_type": doc.document_type,
                "quality_flag": doc.quality_flag,
                "blur_score": doc.blur_score,
            }
            for doc in documents
        ],
    }


@router.post("/{client_id}/approve", response_model=ClientResponse)
def approve_client(client_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.status not in {"ready_for_review", "under_review"}:
        raise HTTPException(
            status_code=409,
            detail="Only clients ready for review or under review can be approved",
        )
    client.status = "approved"
    db.commit()
    db.refresh(client)
    sync_client(
        {"name": client.name, "phone": client.phone, "email": client.email},
        "approved",
    )
    return client


@router.post("/{client_id}/review", response_model=ClientResponse)
def start_client_review(client_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.status != "ready_for_review":
        raise HTTPException(
            status_code=409,
            detail="Only clients ready for review can enter human review",
        )
    client.status = "under_review"
    db.commit()
    db.refresh(client)
    sync_client(
        {"name": client.name, "phone": client.phone, "email": client.email},
        "under_review",
    )
    return client


@router.post("/{client_id}/onboard", response_model=ClientResponse)
def onboard_client(client_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only approved clients can be onboarded",
        )
    client.status = "onboarded"
    db.commit()
    db.refresh(client)
    sync_client(
        {"name": client.name, "phone": client.phone, "email": client.email},
        "onboarded",
    )
    return client


@router.post("/{client_id}/reject", response_model=ClientResponse)
def reject_client(client_id: int, db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    if client.status not in {"under_review", "approved"}:
        raise HTTPException(
            status_code=409,
            detail="Only clients under review or approved can be rejected",
        )
    client.status = "rejected"
    db.commit()
    db.refresh(client)
    sync_client(
        {"name": client.name, "phone": client.phone, "email": client.email},
        "rejected",
    )
    return client
