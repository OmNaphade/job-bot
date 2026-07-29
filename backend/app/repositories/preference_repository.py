import sqlite3
from typing import List

from app.db.database import db_session
from app.models.preference import Preference, PreferenceCreate, PreferenceKind
from app.services.errors import DuplicateResourceError


class PreferenceRepository:
    def list_preferences(self) -> List[Preference]:
        with db_session() as connection:
            rows = connection.execute(
                "SELECT id, keyword, kind, location FROM preferences ORDER BY id DESC"
            ).fetchall()
        return [Preference(**dict(row)) for row in rows]

    def list_keywords_by_kind(self, kind: PreferenceKind) -> List[str]:
        with db_session() as connection:
            rows = connection.execute(
                "SELECT keyword FROM preferences WHERE kind = ? ORDER BY id ASC",
                (kind,),
            ).fetchall()
        return [row["keyword"] for row in rows]

    def create_preference(self, payload: PreferenceCreate) -> Preference:
        with db_session() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO preferences (keyword, kind, location) VALUES (?, ?, ?)",
                    (payload.keyword, payload.kind, payload.location),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateResourceError(
                    f"A '{payload.kind}' preference for keyword '{payload.keyword}' already exists"
                ) from exc
            preference_id = cursor.lastrowid
        return Preference(id=preference_id, **payload.model_dump())

    def delete_preference(self, preference_id: int) -> None:
        with db_session() as connection:
            connection.execute("DELETE FROM preferences WHERE id = ?", (preference_id,))

    def replace_kind(self, kind: PreferenceKind, keywords: List[str]) -> List[str]:
        deduped = list(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))
        with db_session() as connection:
            connection.execute("DELETE FROM preferences WHERE kind = ?", (kind,))
            connection.executemany(
                "INSERT INTO preferences (keyword, kind, location) VALUES (?, ?, NULL)",
                [(keyword, kind) for keyword in deduped],
            )
        return deduped
