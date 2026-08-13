import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.db.database import db_session
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
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
                    (email, password_hash, now),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateResourceError(f"An account with email '{email}' already exists") from exc
            user_id = cursor.lastrowid
        return UserRecord(id=user_id, email=email, password_hash=password_hash, created_at=now)

    def get_by_email(self, email: str) -> Optional[UserRecord]:
        with db_session() as connection:
            row = connection.execute(
                "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return UserRecord(**dict(row)) if row else None

    def get_by_id(self, user_id: int) -> Optional[User]:
        with db_session() as connection:
            row = connection.execute(
                "SELECT id, email, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return User(**dict(row)) if row else None

    def list_all_ids(self) -> list[int]:
        with db_session() as connection:
            rows = connection.execute("SELECT id FROM users ORDER BY id ASC").fetchall()
        return [row["id"] for row in rows]
