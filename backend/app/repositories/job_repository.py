import sqlite3
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
        with db_session() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO jobs (title, company, location, link, source, posted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (payload.title, payload.company, payload.location, payload.link, payload.source, payload.posted_at),
                )
            except sqlite3.IntegrityError as exc:
                raise DuplicateResourceError(f"A job with link '{payload.link}' already exists") from exc
            job_id = cursor.lastrowid
        return Job(id=job_id, **payload.model_dump())

    def create_job_if_new(self, candidate: JobCandidate) -> Optional[Job]:
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
