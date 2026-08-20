from typing import List

import psycopg

from app.db import database
from app.models.preference import Preference, PreferenceCreate, PreferenceKind
from app.services.errors import DuplicateResourceError


class PreferenceRepository:
    def list_preferences(self, user_id: int) -> List[Preference]:
        with database.db_session() as connection:
            rows = connection.execute(
                "SELECT id, keyword, kind, location FROM preferences WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [Preference(**dict(row)) for row in rows]

    def list_keywords_by_kind(self, user_id: int, kind: PreferenceKind) -> List[str]:
        with database.db_session() as connection:
            rows = connection.execute(
                "SELECT keyword FROM preferences WHERE user_id = %s AND kind = %s ORDER BY id ASC",
                (user_id, kind),
            ).fetchall()
        return [row["keyword"] for row in rows]

    def create_preference(self, user_id: int, payload: PreferenceCreate) -> Preference:
        with database.db_session() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO preferences (user_id, keyword, kind, location) VALUES (%s, %s, %s, %s) RETURNING id",
                    (user_id, payload.keyword, payload.kind, payload.location),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise DuplicateResourceError(
                    f"A '{payload.kind}' preference for keyword '{payload.keyword}' already exists"
                ) from exc
            preference_id = cursor.fetchone()["id"]
        return Preference(id=preference_id, **payload.model_dump())

    def delete_preference(self, user_id: int, preference_id: int) -> None:
        with database.db_session() as connection:
            connection.execute(
                "DELETE FROM preferences WHERE id = %s AND user_id = %s", (preference_id, user_id)
            )

    def replace_kind(self, user_id: int, kind: PreferenceKind, keywords: List[str]) -> List[str]:
        deduped = list(dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip()))
        with database.db_session() as connection:
            connection.execute("DELETE FROM preferences WHERE user_id = %s AND kind = %s", (user_id, kind))
            if deduped:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO preferences (user_id, keyword, kind, location) VALUES (%s, %s, %s, NULL)",
                        [(user_id, keyword, kind) for keyword in deduped],
                    )
        return deduped
