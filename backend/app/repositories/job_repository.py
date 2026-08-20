from datetime import datetime, timezone
from typing import List, Optional

import psycopg

from app.db import database
from app.ingestion.models import JobCandidate
from app.models.job import Job, JobCreate
from app.services.errors import DuplicateResourceError


class JobRepository:
    def list_jobs(self, user_id: int) -> List[Job]:
        with database.db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at, logo_url "
                "FROM jobs WHERE user_id = %s ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def create_job(self, user_id: int, payload: JobCreate) -> Job:
        # Manually-added jobs (via POST /jobs) never went through Telegram delivery
        # before notified_at existed, and shouldn't suddenly start being swept into
        # the ingestion notification retry queue -- stamp them as not-applicable.
        with database.db_session() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO jobs (user_id, title, company, location, link, source, posted_at, logo_url, notified_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        payload.title,
                        payload.company,
                        payload.location,
                        payload.link,
                        payload.source,
                        payload.posted_at,
                        payload.logo_url,
                        datetime.now(timezone.utc),
                    ),
                )
            except psycopg.errors.UniqueViolation as exc:
                raise DuplicateResourceError(f"A job with link '{payload.link}' already exists") from exc
            job_id = cursor.fetchone()["id"]
        return Job(id=job_id, **payload.model_dump())

    def create_job_if_new(self, user_id: int, candidate: JobCandidate) -> Optional[Job]:
        # notified_at is left NULL here -- this is the ingestion path, where
        # notification delivery is actually expected. list_unnotified() picks
        # these up (this run and, if delivery fails, on retry in a later run).
        # Dedup is scoped to (user_id, link) -- two different users who both
        # match the same posting each get their own row.
        with database.db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO jobs (user_id, title, company, location, link, source, posted_at, logo_url)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, link) DO NOTHING
                RETURNING id
                """,
                (
                    user_id,
                    candidate.title,
                    candidate.company,
                    candidate.location,
                    candidate.link,
                    candidate.source,
                    candidate.posted_at,
                    candidate.logo_url,
                ),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            job_id = row["id"]
        return Job(
            id=job_id,
            title=candidate.title,
            company=candidate.company,
            location=candidate.location,
            link=candidate.link,
            source=candidate.source,
            posted_at=candidate.posted_at,
            logo_url=candidate.logo_url,
        )

    def list_unnotified(self, user_id: int, limit: int = 200) -> List[Job]:
        """Jobs still awaiting notification delivery: this run's new matches plus
        any left over from a previous run where sending failed partway through.

        Bounded (oldest first) so a multi-day outage doesn't try to flush an
        ever-growing backlog in one run -- whatever doesn't fit within `limit`
        just stays pending and retries next run.
        """
        with database.db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at, logo_url "
                "FROM jobs WHERE user_id = %s AND notified_at IS NULL ORDER BY id ASC LIMIT %s",
                (user_id, limit),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def mark_notified(self, job_ids: List[int]) -> None:
        if not job_ids:
            return
        now = datetime.now(timezone.utc)
        with database.db_session() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(
                    "UPDATE jobs SET notified_at = %s WHERE id = %s",
                    [(now, job_id) for job_id in job_ids],
                )

    def set_embedding(self, job_id: int, embedding: list[float], embedding_model: str) -> None:
        with database.db_session() as connection:
            connection.execute(
                "UPDATE jobs SET embedding = %s, embedding_model = %s, embedded_at = now() WHERE id = %s",
                (embedding, embedding_model, job_id),
            )

    def list_jobs_missing_embedding(self, after_id: int = 0, limit: int = 500) -> List[Job]:
        """Backs the one-off backfill pass (scripts/backfill_job_embeddings.py)
        for jobs ingested before embedding-at-ingestion-time existed, or whose
        embed call failed and was never retried. Not user-scoped -- this is an
        operational sweep across every account's jobs.

        Keyset-paginated on `after_id` rather than always taking the first N
        WHERE embedding IS NULL -- if a job's embed call fails, its embedding
        stays NULL, so a plain "give me the first N still missing" query would
        return the exact same still-failing rows forever instead of paging
        forward. Passing back the highest id seen guarantees progress through
        the table regardless of which individual rows succeeded.
        """
        with database.db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at, logo_url "
                "FROM jobs WHERE embedding IS NULL AND id > %s ORDER BY id ASC LIMIT %s",
                (after_id, limit),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]
