from typing import List

from app.models.job import Job, JobCreate
from app.repositories.job_repository import JobRepository


class JobService:
    def __init__(self, repository: JobRepository | None = None) -> None:
        self.repository = repository or JobRepository()

    def get_jobs(self) -> List[Job]:
        return self.repository.list_jobs()

    def add_job(self, payload: JobCreate) -> Job:
        return self.repository.create_job(payload)
