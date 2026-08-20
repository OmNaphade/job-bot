from datetime import datetime
from typing import Optional

from psycopg.types.json import Jsonb

from app.db import database
from app.models.resume import ResumeProfile


def _row_to_profile(row: dict) -> ResumeProfile:
    return ResumeProfile(
        **row["profile_json"],
        source_filename=row["source_filename"],
        uploaded_at=row["uploaded_at"],
        updated_at=row["updated_at"],
    )


class ResumeRepository:
    def upsert(
        self,
        user_id: int,
        resume_text: str,
        profile_json: dict,
        embedding: list[float],
        embedding_model: str,
        source_filename: Optional[str],
    ) -> ResumeProfile:
        # uploaded_at is set once (first upload) and left alone on reupload --
        # only updated_at moves. ON CONFLICT is the whole "replace on
        # reupload" semantics: one row per user, no history/versioning.
        with database.db_session() as connection:
            row = connection.execute(
                """
                INSERT INTO resume_profiles
                    (user_id, resume_text, profile_json, embedding, embedding_model, source_filename, uploaded_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, now(), now())
                ON CONFLICT (user_id) DO UPDATE SET
                    resume_text = excluded.resume_text,
                    profile_json = excluded.profile_json,
                    embedding = excluded.embedding,
                    embedding_model = excluded.embedding_model,
                    source_filename = excluded.source_filename,
                    updated_at = now()
                RETURNING profile_json, source_filename, uploaded_at, updated_at
                """,
                (user_id, resume_text, Jsonb(profile_json), embedding, embedding_model, source_filename),
            ).fetchone()
        return _row_to_profile(row)

    def get(self, user_id: int) -> Optional[ResumeProfile]:
        with database.db_session() as connection:
            row = connection.execute(
                "SELECT profile_json, source_filename, uploaded_at, updated_at FROM resume_profiles WHERE user_id = %s",
                (user_id,),
            ).fetchone()
        return _row_to_profile(row) if row else None

    def get_embedding(self, user_id: int) -> Optional[list[float]]:
        """The raw embedding vector for a user's resume -- not exposed on
        ResumeProfile (the public API/DB shape), only used internally by
        MatchingService to run the similarity query.

        register_vector() (app/db/database.py) makes reading a `vector`
        column return a numpy array, not a plain list -- converted to native
        Python floats here so callers get the `list[float]` this signature
        promises, not numpy.float32 leaking out.
        """
        with database.db_session() as connection:
            row = connection.execute(
                "SELECT embedding FROM resume_profiles WHERE user_id = %s",
                (user_id,),
            ).fetchone()
        return [float(value) for value in row["embedding"]] if row else None

    def delete(self, user_id: int) -> None:
        with database.db_session() as connection:
            connection.execute("DELETE FROM resume_profiles WHERE user_id = %s", (user_id,))

    def count_uploads_since(self, user_id: int, since: datetime) -> int:
        with database.db_session() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM resume_upload_events WHERE user_id = %s AND uploaded_at > %s",
                (user_id, since),
            ).fetchone()
        return row["count"]

    def record_upload_event(self, user_id: int) -> None:
        with database.db_session() as connection:
            connection.execute(
                "INSERT INTO resume_upload_events (user_id, uploaded_at) VALUES (%s, now())",
                (user_id,),
            )
