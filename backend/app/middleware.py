from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


def add_cors_middleware(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
