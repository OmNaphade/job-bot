from app.ingestion.services.embedding_service import EmbeddingService
from app.ingestion.models import JobCandidate
from app.models.job import Job
from app.repositories.job_repository import JobRepository


class _FakeGeminiClient:
    def __init__(self, embedding: list[float] | None = None, fail: bool = False):
        self.embedding = embedding or [0.2] * 768
        self.fail = fail
        self.embed_calls: list[str] = []

    def embed_text(self, text: str) -> list[float]:
        if self.fail:
            raise RuntimeError("Gemini is down")
        self.embed_calls.append(text)
        return self.embedding


def _persist_job(user_id: int) -> Job:
    return JobRepository().create_job_if_new(
        user_id,
        JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://x.com/1", source="rss"),
    )


def test_embed_job_persists_the_embedding(test_user):
    job = _persist_job(test_user.id)
    fake_client = _FakeGeminiClient()
    service = EmbeddingService(ai_client=fake_client)

    service.embed_job(job)

    assert job.id not in {j.id for j in JobRepository().list_jobs_missing_embedding()}
    assert fake_client.embed_calls == ["Backend Engineer\nAcme\nRemote"]


def test_embed_job_skips_jobs_without_an_id():
    service = EmbeddingService(ai_client=_FakeGeminiClient())
    job = Job(title="x", company="y", location="z", link="l", source="s")  # id=None

    service.embed_job(job)  # must not raise


def test_embed_job_swallows_ai_failures(test_user):
    job = _persist_job(test_user.id)
    service = EmbeddingService(ai_client=_FakeGeminiClient(fail=True))

    service.embed_job(job)  # must not raise

    assert job.id in {j.id for j in JobRepository().list_jobs_missing_embedding()}


def test_embed_job_swallows_missing_api_key(test_user, monkeypatch):
    import dataclasses

    from app.ai import gemini_client as gemini_client_module

    monkeypatch.setattr(
        gemini_client_module, "settings", dataclasses.replace(gemini_client_module.settings, google_api_key=None)
    )
    job = _persist_job(test_user.id)
    service = EmbeddingService()  # no ai_client override -- constructs GeminiClient() lazily

    service.embed_job(job)  # must not raise

    assert job.id in {j.id for j in JobRepository().list_jobs_missing_embedding()}


def test_embed_jobs_processes_every_job_independently(test_user):
    repo = JobRepository()
    job1 = repo.create_job_if_new(
        test_user.id,
        JobCandidate(title="Backend Engineer", company="Acme", location="Remote", link="https://x.com/1", source="rss"),
    )
    job2 = repo.create_job_if_new(
        test_user.id,
        JobCandidate(title="Frontend Engineer", company="Acme", location="Remote", link="https://x.com/2", source="rss"),
    )
    service = EmbeddingService(ai_client=_FakeGeminiClient())

    service.embed_jobs([job1, job2])

    missing_ids = {j.id for j in repo.list_jobs_missing_embedding()}
    assert job1.id not in missing_ids
    assert job2.id not in missing_ids
