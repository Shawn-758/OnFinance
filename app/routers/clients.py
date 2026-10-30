from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Client, Document
from app.db.session import get_db
from app.schemas.ingest import ClientResponse


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
