from typing import List

from app.models.job import Job, JobCreate
from app.repositories.job_repository import JobRepository


class JobService:
    def __init__(self, repository: JobRepository | None = None) -> None:
        self.repository = repository or JobRepository()

    def get_jobs(self, user_id: int) -> List[Job]:
        return self.repository.list_jobs(user_id)

    def add_job(self, user_id: int, payload: JobCreate) -> Job:
        return self.repository.create_job(user_id, payload)
