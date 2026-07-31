import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from app.db.database import db_session
from app.ingestion.models import JobCandidate
from app.models.job import Job, JobCreate
from app.services.errors import DuplicateResourceError


class JobRepository:
    def list_jobs(self) -> List[Job]:
        with db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at FROM jobs ORDER BY id DESC"
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def create_job(self, payload: JobCreate) -> Job:
        # Manually-added jobs (via POST /jobs) never went through Telegram delivery
        # before notified_at existed, and shouldn't suddenly start being swept into
        # the ingestion notification retry queue -- stamp them as not-applicable.
        with db_session() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO jobs (title, company, location, link, source, posted_at, notified_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload.title,
                        payload.company,
                        payload.location,
                        payload.link,
                        payload.source,
                        payload.posted_at,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateResourceError(f"A job with link '{payload.link}' already exists") from exc
            job_id = cursor.lastrowid
        return Job(id=job_id, **payload.model_dump())

    def create_job_if_new(self, candidate: JobCandidate) -> Optional[Job]:
        # notified_at is left NULL here -- this is the ingestion path, where
        # Telegram delivery is actually expected. list_unnotified() picks these
        # up (this run and, if delivery fails, on retry in a later run).
        with db_session() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO jobs (title, company, location, link, source, posted_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (candidate.title, candidate.company, candidate.location, candidate.link, candidate.source, candidate.posted_at),
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
        )

    def list_unnotified(self, limit: int = 200) -> List[Job]:
        """Jobs still awaiting Telegram delivery: this run's new matches plus any
        left over from a previous run where sending failed partway through.

        Bounded (oldest first) so a multi-day Telegram outage doesn't try to
        flush an ever-growing backlog in one run -- whatever doesn't fit
        within `limit` just stays pending and retries next run.
        """
        with db_session() as connection:
            rows = connection.execute(
                "SELECT id, title, company, location, link, source, posted_at "
                "FROM jobs WHERE notified_at IS NULL ORDER BY id ASC LIMIT ?",
                (limit,),
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
