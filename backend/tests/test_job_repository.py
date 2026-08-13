import pytest

from app.core.security import hash_password
from app.ingestion.models import JobCandidate
from app.models.job import JobCreate
from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository
from app.services.errors import DuplicateResourceError


def _job_payload(link: str = "https://example.com/jobs/1") -> JobCreate:
    return JobCreate(title="Backend Engineer", company="Acme", location="Remote", link=link, source="manual")


def test_create_job_persists_and_returns_id(test_user):
    job = JobRepository().create_job(test_user.id, _job_payload())
    assert job.id is not None
    assert job.title == "Backend Engineer"


def test_create_job_raises_on_duplicate_link(test_user):
    repo = JobRepository()
    repo.create_job(test_user.id, _job_payload())
    with pytest.raises(DuplicateResourceError):
        repo.create_job(test_user.id, _job_payload())


def test_create_job_if_new_returns_none_for_existing_link(test_user):
    repo = JobRepository()
    repo.create_job(test_user.id, _job_payload())

    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/1", source="rss")
    result = repo.create_job_if_new(test_user.id, candidate)

    assert result is None


def test_create_job_if_new_persists_a_genuinely_new_link(test_user):
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")

    result = JobRepository().create_job_if_new(test_user.id, candidate)

    assert result is not None
    assert result.link == "https://example.com/jobs/2"


def test_list_jobs_returns_newest_first(test_user):
    repo = JobRepository()
    repo.create_job(test_user.id, _job_payload("https://example.com/jobs/1"))
    repo.create_job(test_user.id, _job_payload("https://example.com/jobs/2"))

    jobs = repo.list_jobs(test_user.id)

    assert [job.link for job in jobs] == ["https://example.com/jobs/2", "https://example.com/jobs/1"]


def test_list_jobs_only_returns_the_calling_users_jobs(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    JobRepository().create_job(test_user.id, _job_payload("https://example.com/jobs/mine"))
    JobRepository().create_job(other_user.id, _job_payload("https://example.com/jobs/theirs"))

    jobs = JobRepository().list_jobs(test_user.id)

    assert [job.link for job in jobs] == ["https://example.com/jobs/mine"]


def test_two_users_can_each_have_a_row_for_the_same_link(test_user, tmp_db):
    """Regression test for the UNIQUE(user_id, link) migration -- two different
    users who both match the same posting must each get their own row, not
    collide on a single globally-unique link."""
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/shared", source="rss")

    first = JobRepository().create_job_if_new(test_user.id, candidate)
    second = JobRepository().create_job_if_new(other_user.id, candidate)

    assert first is not None
    assert second is not None
    assert first.id != second.id
    assert [job.link for job in JobRepository().list_jobs(test_user.id)] == ["https://example.com/jobs/shared"]
    assert [job.link for job in JobRepository().list_jobs(other_user.id)] == ["https://example.com/jobs/shared"]


def test_create_job_marks_notified_at_so_it_skips_the_delivery_queue(test_user):
    JobRepository().create_job(test_user.id, _job_payload())

    assert JobRepository().list_unnotified(test_user.id) == []


def test_create_job_if_new_leaves_notified_at_null_for_the_delivery_queue(test_user):
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")
    JobRepository().create_job_if_new(test_user.id, candidate)

    pending = JobRepository().list_unnotified(test_user.id)

    assert [job.link for job in pending] == ["https://example.com/jobs/2"]


def test_mark_notified_removes_jobs_from_the_unnotified_queue(test_user):
    repo = JobRepository()
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")
    created = repo.create_job_if_new(test_user.id, candidate)

    repo.mark_notified([created.id])

    assert repo.list_unnotified(test_user.id) == []


def test_mark_notified_with_no_ids_does_not_raise(tmp_db):
    JobRepository().mark_notified([])  # no-op, must not error


def test_create_job_if_new_persists_logo_url(test_user):
    candidate = JobCandidate(
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        link="https://example.com/jobs/2",
        source="rss",
        logo_url="https://logo.clearbit.com/acme.com",
    )
    result = JobRepository().create_job_if_new(test_user.id, candidate)

    assert result.logo_url == "https://logo.clearbit.com/acme.com"
    assert JobRepository().list_jobs(test_user.id)[0].logo_url == "https://logo.clearbit.com/acme.com"


def test_create_job_if_new_leaves_logo_url_none_when_absent(test_user):
    candidate = JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://example.com/jobs/2", source="rss")
    result = JobRepository().create_job_if_new(test_user.id, candidate)

    assert result.logo_url is None


def test_list_unnotified_is_bounded_and_returns_oldest_first(test_user):
    repo = JobRepository()
    for i in range(5):
        repo.create_job_if_new(
            test_user.id,
            JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link=f"https://example.com/jobs/{i}", source="rss"),
        )

    pending = repo.list_unnotified(test_user.id, limit=3)

    assert [job.link for job in pending] == [
        "https://example.com/jobs/0",
        "https://example.com/jobs/1",
        "https://example.com/jobs/2",
    ]
