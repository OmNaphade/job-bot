import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.db.database import db_session


class SessionRepository:
    def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.session_ttl_days)
        with db_session() as connection:
            connection.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, user_id, now.isoformat(), expires_at.isoformat()),
            )
        return token

    def get_valid_session(self, token: str) -> Optional[int]:
        with db_session() as connection:
            row = connection.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token = ?",
                (token,),
            ).fetchone()
        if row is None:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        return row["user_id"]

    def delete(self, token: str) -> None:
        with db_session() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
