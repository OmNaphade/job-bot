import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.db import database


class SessionRepository:
    def create(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.session_ttl_days)
        with database.db_session() as connection:
            connection.execute(
                "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (%s, %s, %s, %s)",
                (token, user_id, now, expires_at),
            )
        return token

    def get_valid_session(self, token: str) -> Optional[int]:
        with database.db_session() as connection:
            row = connection.execute(
                "SELECT user_id, expires_at FROM sessions WHERE token = %s",
                (token,),
            ).fetchone()
        if row is None:
            return None
        # psycopg returns a timezone-aware datetime for TIMESTAMPTZ columns
        # directly -- no string parsing needed the way SQLite's TEXT storage
        # required.
        if row["expires_at"] <= datetime.now(timezone.utc):
            return None
        return row["user_id"]

    def delete(self, token: str) -> None:
        with database.db_session() as connection:
            connection.execute("DELETE FROM sessions WHERE token = %s", (token,))
