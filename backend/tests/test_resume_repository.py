from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.repositories.resume_repository import ResumeRepository
from app.repositories.user_repository import UserRepository


def _embedding(seed: float = 0.1) -> list[float]:
    return [seed] * 768


def _profile_json(**overrides) -> dict:
    base = {
        "skills": ["Python", "Postgres"],
        "titles": ["Backend Engineer"],
        "years_experience": 5.0,
        "seniority": "senior",
        "locations": ["Remote"],
        "education": ["B.Sc. Computer Science"],
    }
    base.update(overrides)
    return base


def test_upsert_persists_a_new_profile(test_user):
    profile = ResumeRepository().upsert(
        user_id=test_user.id,
        resume_text="Jane Doe resume text",
        profile_json=_profile_json(),
        embedding=_embedding(),
        embedding_model="text-embedding-004",
        source_filename="resume.pdf",
    )

    assert profile.skills == ["Python", "Postgres"]
    assert profile.titles == ["Backend Engineer"]
    assert profile.years_experience == 5.0
    assert profile.seniority == "senior"
    assert profile.source_filename == "resume.pdf"
    assert profile.uploaded_at is not None
    assert profile.updated_at is not None


def test_get_returns_none_when_no_profile_exists(test_user):
    assert ResumeRepository().get(test_user.id) is None


def test_get_returns_the_persisted_profile(test_user):
    repo = ResumeRepository()
    repo.upsert(
        user_id=test_user.id,
        resume_text="text",
        profile_json=_profile_json(),
        embedding=_embedding(),
        embedding_model="text-embedding-004",
        source_filename="resume.pdf",
    )

    fetched = repo.get(test_user.id)

    assert fetched.skills == ["Python", "Postgres"]
    assert fetched.source_filename == "resume.pdf"


def test_upsert_replaces_rather_than_duplicates_on_reupload(test_user):
    repo = ResumeRepository()
    first = repo.upsert(
        user_id=test_user.id,
        resume_text="first resume",
        profile_json=_profile_json(skills=["Python"]),
        embedding=_embedding(0.1),
        embedding_model="text-embedding-004",
        source_filename="v1.pdf",
    )
    second = repo.upsert(
        user_id=test_user.id,
        resume_text="second resume",
        profile_json=_profile_json(skills=["Go", "Kubernetes"]),
        embedding=_embedding(0.2),
        embedding_model="text-embedding-004",
        source_filename="v2.pdf",
    )

    fetched = repo.get(test_user.id)
    assert fetched.skills == ["Go", "Kubernetes"]
    assert fetched.source_filename == "v2.pdf"
    # uploaded_at is set once on first upload and never moves; updated_at
    # advances on every reupload -- see ResumeRepository.upsert's docstring.
    assert first.uploaded_at == second.uploaded_at
    assert second.updated_at >= first.updated_at


def test_delete_removes_the_profile(test_user):
    repo = ResumeRepository()
    repo.upsert(
        user_id=test_user.id,
        resume_text="text",
        profile_json=_profile_json(),
        embedding=_embedding(),
        embedding_model="text-embedding-004",
        source_filename="resume.pdf",
    )

    repo.delete(test_user.id)

    assert repo.get(test_user.id) is None


def test_delete_when_no_profile_exists_does_not_raise(test_user):
    ResumeRepository().delete(test_user.id)  # no-op, must not error


def test_profiles_are_isolated_per_user(test_user):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = ResumeRepository()
    repo.upsert(
        user_id=test_user.id,
        resume_text="mine",
        profile_json=_profile_json(skills=["Python"]),
        embedding=_embedding(),
        embedding_model="text-embedding-004",
        source_filename="mine.pdf",
    )
    repo.upsert(
        user_id=other_user.id,
        resume_text="theirs",
        profile_json=_profile_json(skills=["Java"]),
        embedding=_embedding(),
        embedding_model="text-embedding-004",
        source_filename="theirs.pdf",
    )

    assert repo.get(test_user.id).skills == ["Python"]
    assert repo.get(other_user.id).skills == ["Java"]


def test_count_uploads_since_counts_only_events_after_the_cutoff(test_user):
    repo = ResumeRepository()
    repo.record_upload_event(test_user.id)
    repo.record_upload_event(test_user.id)

    since_past = datetime.now(timezone.utc) - timedelta(days=1)
    since_future = datetime.now(timezone.utc) + timedelta(days=1)

    assert repo.count_uploads_since(test_user.id, since_past) == 2
    assert repo.count_uploads_since(test_user.id, since_future) == 0


def test_count_uploads_since_is_scoped_per_user(test_user):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = ResumeRepository()
    repo.record_upload_event(test_user.id)

    since = datetime.now(timezone.utc) - timedelta(days=1)

    assert repo.count_uploads_since(test_user.id, since) == 1
    assert repo.count_uploads_since(other_user.id, since) == 0
