import logging

from app.ai.gemini_client import GeminiClient
from app.core.config import settings
from app.models.job import Job
from app.repositories.job_repository import JobRepository

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Embeds jobs once, at ingestion time, so GET /matches never has to call
    Gemini per comparison -- matching is pure vector-distance SQL against
    already-stored embeddings. See MatchingService/MatchingRepository."""

    def __init__(self, ai_client: GeminiClient | None = None, repository: JobRepository | None = None) -> None:
        self.repository = repository or JobRepository()
        # Constructed lazily -- GeminiClient() raises if GOOGLE_API_KEY is
        # unset, and embedding failures are caught per-job below rather than
        # aborting the whole ingestion run.
        self._ai_client = ai_client

    def _get_ai_client(self) -> GeminiClient:
        if self._ai_client is None:
            self._ai_client = GeminiClient()
        return self._ai_client

    def embed_jobs(self, jobs: list[Job]) -> None:
        for job in jobs:
            self.embed_job(job)

    def embed_job(self, job: Job) -> None:
        if job.id is None:
            return
        try:
            ai_client = self._get_ai_client()
            text = f"{job.title}\n{job.company}\n{job.location}"
            embedding = ai_client.embed_text(text)
            self.repository.set_embedding(job.id, embedding, settings.gemini_embedding_model)
        except Exception:
            # A job still gets inserted and still serves keyword-based alerts
            # even if this fails (Gemini quota/outage) -- it just won't show
            # up in personalized matches until the next backfill sweep picks
            # it up (scripts/backfill_job_embeddings.py). Never let an
            # embedding failure abort the ingestion run itself.
            logger.exception("Failed to embed job id=%s -- it will still serve keyword alerts", job.id)
