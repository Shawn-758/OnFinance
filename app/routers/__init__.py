from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router
from app.routers.clients import router as clients_router

__all__ = ["health_router", "ingest_router", "clients_router"]
