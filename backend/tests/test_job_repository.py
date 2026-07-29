import pytest

from app.ingestion.models import JobCandidate
from app.models.job import JobCreate
from app.repositories.job_repository import JobRepository
from app.services.errors import DuplicateResourceError


def _job_payload(link: str = "https://example.com/jobs/1") -> JobCreate:
    return JobCreate(title="Backend Engineer", company="Acme", location="Remote", link=link, source="manual")


def test_create_job_persists_and_returns_id(tmp_db):
    job = JobRepository().create_job(_job_payload())
    assert job.id is not None
    assert job.title == "Backend Engineer"


def test_create_job_raises_on_duplicate_link(tmp_db):
    repo = JobRepository()
    repo.create_job(_job_payload())
    with pytest.raises(DuplicateResourceError):
        repo.create_job(_job_payload())


def test_create_job_if_new_returns_none_for_existing_link(tmp_db):
    repo = JobRepository()
    repo.create_job(_job_payload())

    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/1", source="rss")
    result = repo.create_job_if_new(candidate)

    assert result is None


def test_create_job_if_new_persists_a_genuinely_new_link(tmp_db):
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")

    result = JobRepository().create_job_if_new(candidate)

    assert result is not None
    assert result.link == "https://example.com/jobs/2"


def test_list_jobs_returns_newest_first(tmp_db):
    repo = JobRepository()
    repo.create_job(_job_payload("https://example.com/jobs/1"))
    repo.create_job(_job_payload("https://example.com/jobs/2"))

    jobs = repo.list_jobs()

    assert [job.link for job in jobs] == ["https://example.com/jobs/2", "https://example.com/jobs/1"]
