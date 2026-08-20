import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db import database
from app.middleware import add_cors_middleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic (`alembic upgrade head`, run as a deploy step --
    # see deploy/oci_deploy_db.sh), not created here. Opening the pool eagerly
    # at startup just means a misconfigured DATABASE_URL or unreachable DB
    # fails loudly on boot instead of on the first request.
    #
    # This process (the API) no longer schedules ingestion itself -- that's
    # VM2's job-alert-worker.timer now (see deploy/oci_deploy_db.sh), so there
    # is exactly one scheduling mechanism instead of two that could double-fire
    # if both were ever left running at once.
    database.get_pool().wait()
    yield
    database.get_pool().close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
add_cors_middleware(app)
app.include_router(router)
