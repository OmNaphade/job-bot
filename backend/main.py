import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import settings
from app.db.database import init_db
from app.ingestion import scheduler
from app.middleware import add_cors_middleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
add_cors_middleware(app)
app.include_router(router)
