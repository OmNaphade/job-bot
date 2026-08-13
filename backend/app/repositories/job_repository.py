import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from app.db.database import db_session
from app.ingestion.models import JobCandidate
from app.models.job import Job, JobCreate
from app.services.errors import DuplicateResourceError


class JobRepository:
    def list_jobs(self, user_id: int) -> List[Job]:
        with db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at, logo_url "
                "FROM jobs WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def create_job(self, user_id: int, payload: JobCreate) -> Job:
        # Manually-added jobs (via POST /jobs) never went through Telegram delivery
        # before notified_at existed, and shouldn't suddenly start being swept into
        # the ingestion notification retry queue -- stamp them as not-applicable.
        with db_session() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO jobs (user_id, title, company, location, link, source, posted_at, logo_url, notified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateResourceError(f"A job with link '{payload.link}' already exists") from exc
            job_id = cursor.lastrowid
        return Job(id=job_id, **payload.model_dump())

    def create_job_if_new(self, user_id: int, candidate: JobCandidate) -> Optional[Job]:
        # notified_at is left NULL here -- this is the ingestion path, where
        # notification delivery is actually expected. list_unnotified() picks
        # these up (this run and, if delivery fails, on retry in a later run).
        # Dedup is scoped to (user_id, link) -- two different users who both
        # match the same posting each get their own row.
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO jobs (user_id, title, company, location, link, source, posted_at, logo_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            if cursor.rowcount == 0:
                return None
            job_id = cursor.lastrowid
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
        with db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at, logo_url "
                "FROM jobs WHERE user_id = ? AND notified_at IS NULL ORDER BY id ASC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def mark_notified(self, job_ids: List[int]) -> None:
        if not job_ids:
            return
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as connection:
            connection.executemany(
                "UPDATE jobs SET notified_at = ? WHERE id = ?",
                [(now, job_id) for job_id in job_ids],
            )
