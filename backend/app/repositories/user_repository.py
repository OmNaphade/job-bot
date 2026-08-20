from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import psycopg

from app.db import database
from app.models.user import User
from app.services.errors import DuplicateResourceError


@dataclass(frozen=True)
class UserRecord:
    """Internal representation including the password hash -- never exposed
    directly over the API. AuthService converts to the public `User` model."""

    id: int
    email: str
    password_hash: str
    created_at: str

    def to_user(self) -> User:
        return User(id=self.id, email=self.email, created_at=self.created_at)


class UserRepository:
    def create(self, email: str, password_hash: str) -> UserRecord:
        now = datetime.now(timezone.utc)
        with database.db_session() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO users (email, password_hash, created_at) VALUES (%s, %s, %s) RETURNING id",
                    (email, password_hash, now),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise DuplicateResourceError(f"An account with email '{email}' already exists") from exc
            user_id = cursor.fetchone()["id"]
        return UserRecord(id=user_id, email=email, password_hash=password_hash, created_at=now.isoformat())

    def get_by_email(self, email: str) -> Optional[UserRecord]:
        with database.db_session() as connection:
            row = connection.execute(
                "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
                (email,),
            ).fetchone()
        if row is None:
            return None
        return UserRecord(**{**row, "created_at": row["created_at"].isoformat()})

    def get_by_id(self, user_id: int) -> Optional[User]:
        with database.db_session() as connection:
            row = connection.execute(
                "SELECT id, email, created_at FROM users WHERE id = %s",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return User(**{**row, "created_at": row["created_at"].isoformat()})

    def list_all_ids(self) -> list[int]:
        with database.db_session() as connection:
            rows = connection.execute("SELECT id FROM users ORDER BY id ASC").fetchall()
        return [row["id"] for row in rows]
