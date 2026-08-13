import bcrypt
from fastapi import Header, HTTPException

from app.models.user import User
from app.repositories.session_repository import SessionRepository
from app.repositories.user_repository import UserRepository

_INVALID_SESSION_DETAIL = "Missing, invalid, or expired session"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash -- treat as "doesn't match" rather than a 500.
        return False


def get_current_user(authorization: str | None = Header(default=None)) -> User:
    """Resolves the session token in `Authorization: Bearer <token>` to a User.

    Structurally the same shape as the old require_api_key gate -- one Header
    dependency, one 401 on failure -- except this resolves a real identity
    instead of a boolean, and every protected route now depends on it.
    """
    token = extract_bearer_token(authorization)
    user_id = SessionRepository().get_valid_session(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail=_INVALID_SESSION_DETAIL)
    user = UserRepository().get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail=_INVALID_SESSION_DETAIL)
    return user


def extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail=_INVALID_SESSION_DETAIL)
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail=_INVALID_SESSION_DETAIL)
    return token
