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


def test_create_job_marks_notified_at_so_it_skips_the_delivery_queue(tmp_db):
    JobRepository().create_job(_job_payload())

    assert JobRepository().list_unnotified() == []


def test_create_job_if_new_leaves_notified_at_null_for_the_delivery_queue(tmp_db):
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")
    JobRepository().create_job_if_new(candidate)

    pending = JobRepository().list_unnotified()

    assert [job.link for job in pending] == ["https://example.com/jobs/2"]


def test_mark_notified_removes_jobs_from_the_unnotified_queue(tmp_db):
    repo = JobRepository()
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")
    created = repo.create_job_if_new(candidate)

    repo.mark_notified([created.id])

    assert repo.list_unnotified() == []


def test_mark_notified_with_no_ids_does_not_raise(tmp_db):
    JobRepository().mark_notified([])  # no-op, must not error


def test_list_unnotified_is_bounded_and_returns_oldest_first(tmp_db):
    repo = JobRepository()
    for i in range(5):
        repo.create_job_if_new(
            JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link=f"https://example.com/jobs/{i}", source="rss")
        )

    pending = repo.list_unnotified(limit=3)

    assert [job.link for job in pending] == [
        "https://example.com/jobs/0",
        "https://example.com/jobs/1",
        "https://example.com/jobs/2",
    ]
