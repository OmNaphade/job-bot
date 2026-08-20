from app.ingestion.models import JobCandidate
from app.repositories.job_repository import JobRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.matching_service import MatchingService


def _embedding(seed: float = 0.1) -> list[float]:
    return [seed] * 768


def _upload_resume(user_id: int) -> None:
    ResumeRepository().upsert(
        user_id=user_id,
        resume_text="text",
        profile_json={
            "skills": ["Python"],
            "titles": ["Backend Engineer"],
            "years_experience": 5.0,
            "seniority": "senior",
            "locations": ["Remote"],
            "education": [],
        },
        embedding=_embedding(),
        embedding_model="text-embedding-004",
        source_filename="resume.pdf",
    )


def test_get_matches_returns_empty_list_without_a_resume(test_user):
    assert MatchingService().get_matches(test_user.id) == []


def test_get_matches_returns_ranked_jobs_once_a_resume_exists(test_user):
    _upload_resume(test_user.id)
    job = JobRepository().create_job_if_new(
        test_user.id,
        JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://x.com/1", source="rss"),
    )
    JobRepository().set_embedding(job.id, _embedding(), "text-embedding-004")

    matches = MatchingService().get_matches(test_user.id)

    assert len(matches) == 1
    assert matches[0].id == job.id
    assert matches[0].match_score > 0.99


def test_get_matches_passes_through_limit_and_offset(test_user):
    _upload_resume(test_user.id)
    for i in range(3):
        job = JobRepository().create_job_if_new(
            test_user.id,
            JobCandidate(title=f"Job {i}", company="Acme", location="Remote", link=f"https://x.com/{i}", source="rss"),
        )
        JobRepository().set_embedding(job.id, _embedding(), "text-embedding-004")

    matches = MatchingService().get_matches(test_user.id, limit=1, offset=1)

    assert len(matches) == 1
