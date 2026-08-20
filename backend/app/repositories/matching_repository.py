from typing import List

from pgvector.utils import Vector

from app.db import database
from app.models.match import JobMatch


class MatchingRepository:
    def find_matches(self, user_id: int, resume_embedding: list[float], limit: int, offset: int) -> List[JobMatch]:
        # Matching stays strictly per-user (v1 scope, see bot_docs/ARCHITECTURE.md):
        # this only ranks jobs that user's own keyword/source ingestion already
        # pulled in, same UNIQUE(user_id, link) pool the alert pipeline uses --
        # not a shared/global job pool.
        #
        # The `<=>` (cosine distance) operator needs both sides to resolve to
        # `vector` -- a plain Python list parameter adapts to a Postgres array
        # by default and fails with "operator does not exist: vector <=>
        # double precision[]", confirmed empirically against a live pgvector
        # instance. Wrapping in pgvector.utils.Vector picks up the dumper
        # `register_vector()` (app/db/database.py) registers for that type.
        vector_param = Vector(resume_embedding)
        with database.db_session() as connection:
            rows = connection.execute(
                """
                SELECT id, title, company, location, link, source, posted_at, logo_url,
                       1 - (embedding <=> %(embedding)s) AS match_score
                FROM jobs
                WHERE user_id = %(user_id)s AND embedding IS NOT NULL
                ORDER BY embedding <=> %(embedding)s
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                {"embedding": vector_param, "user_id": user_id, "limit": limit, "offset": offset},
            ).fetchall()
        return [JobMatch(**dict(row)) for row in rows]
