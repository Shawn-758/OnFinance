from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db.init_db import init_db
from app.routers.clients import router as clients_router
from app.routers.health import router as health_router
from app.routers.ingest import router as ingest_router


settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(clients_router)
