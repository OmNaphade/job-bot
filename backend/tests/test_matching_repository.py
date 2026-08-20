from app.core.security import hash_password
from app.ingestion.models import JobCandidate
from app.repositories.job_repository import JobRepository
from app.repositories.matching_repository import MatchingRepository
from app.repositories.user_repository import UserRepository


def _vector_with_one_at(index: int, dim: int = 768) -> list[float]:
    vector = [0.0] * dim
    vector[index] = 1.0
    return vector


def _make_job(user_id: int, link: str, title: str = "Backend Engineer"):
    return JobRepository().create_job_if_new(
        user_id, JobCandidate(title=title, company="Acme", location="Remote", link=link, source="rss")
    )


def test_find_matches_ranks_closer_embeddings_first(test_user):
    close_job = _make_job(test_user.id, "https://x.com/close", title="Close Match")
    far_job = _make_job(test_user.id, "https://x.com/far", title="Far Match")
    JobRepository().set_embedding(close_job.id, _vector_with_one_at(0), "text-embedding-004")
    JobRepository().set_embedding(far_job.id, _vector_with_one_at(1), "text-embedding-004")

    resume_embedding = _vector_with_one_at(0)
    matches = MatchingRepository().find_matches(test_user.id, resume_embedding, limit=20, offset=0)

    assert [m.title for m in matches] == ["Close Match", "Far Match"]
    assert matches[0].match_score > matches[1].match_score
    assert matches[0].match_score > 0.99  # identical vectors -> cosine distance ~0 -> score ~1


def test_find_matches_excludes_jobs_without_an_embedding(test_user):
    _make_job(test_user.id, "https://x.com/unembedded")
    embedded_job = _make_job(test_user.id, "https://x.com/embedded")
    JobRepository().set_embedding(embedded_job.id, _vector_with_one_at(0), "text-embedding-004")

    matches = MatchingRepository().find_matches(test_user.id, _vector_with_one_at(0), limit=20, offset=0)

    assert [m.id for m in matches] == [embedded_job.id]


def test_find_matches_is_scoped_per_user(test_user):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    mine = _make_job(test_user.id, "https://x.com/mine")
    theirs = _make_job(other_user.id, "https://x.com/theirs")
    JobRepository().set_embedding(mine.id, _vector_with_one_at(0), "text-embedding-004")
    JobRepository().set_embedding(theirs.id, _vector_with_one_at(0), "text-embedding-004")

    matches = MatchingRepository().find_matches(test_user.id, _vector_with_one_at(0), limit=20, offset=0)

    assert [m.id for m in matches] == [mine.id]


def test_find_matches_respects_limit_and_offset(test_user):
    for i in range(5):
        job = _make_job(test_user.id, f"https://x.com/{i}", title=f"Job {i}")
        JobRepository().set_embedding(job.id, _vector_with_one_at(0), "text-embedding-004")

    page1 = MatchingRepository().find_matches(test_user.id, _vector_with_one_at(0), limit=2, offset=0)
    page2 = MatchingRepository().find_matches(test_user.id, _vector_with_one_at(0), limit=2, offset=2)

    assert len(page1) == 2
    assert len(page2) == 2
    assert {m.id for m in page1}.isdisjoint({m.id for m in page2})
