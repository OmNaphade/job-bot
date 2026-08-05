import hmac

from fastapi import Header, HTTPException

from app.core.config import settings


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Opt-in auth: a no-op unless API_KEY is set in the environment.

    Applied to every route except /health -- see routes.py.
    """
    if not settings.api_key:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key")
