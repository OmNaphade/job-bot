import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.ai.gemini_client import GeminiClient
from app.ai.pdf_extractor import extract_text
from app.core.config import settings
from app.models.resume import ResumeProfile
from app.repositories.resume_repository import ResumeRepository
from app.services.errors import AIExtractionError, ResumeUploadLimitExceeded

logger = logging.getLogger(__name__)


class ResumeService:
    def __init__(self, repository: ResumeRepository | None = None, ai_client: GeminiClient | None = None) -> None:
        self.repository = repository or ResumeRepository()
        # Constructed lazily, not here -- GeminiClient() raises if
        # GOOGLE_API_KEY is unset, and callers that only ever call
        # get_profile()/delete() shouldn't need a key configured at all.
        self._ai_client = ai_client

    def _get_ai_client(self) -> GeminiClient:
        if self._ai_client is None:
            self._ai_client = GeminiClient()
        return self._ai_client

    def upload(self, user_id: int, pdf_bytes: bytes, filename: Optional[str]) -> ResumeProfile:
        # Cheap check first -- fail before spending any Gemini quota.
        since = datetime.now(timezone.utc) - timedelta(days=1)
        upload_count = self.repository.count_uploads_since(user_id, since)
        if upload_count >= settings.resume_upload_daily_cap:
            raise ResumeUploadLimitExceeded(
                f"Daily resume upload limit ({settings.resume_upload_daily_cap}) reached -- try again tomorrow."
            )

        resume_text = extract_text(pdf_bytes)
        if not resume_text:
            raise AIExtractionError("Couldn't extract any text from that PDF -- is it a scanned image rather than text?")

        try:
            ai_client = self._get_ai_client()
            profile_json = ai_client.extract_resume_profile(resume_text)
            embedding = ai_client.embed_text(resume_text)
        except Exception as exc:
            logger.exception("Gemini call failed while processing a resume upload for user %s", user_id)
            raise AIExtractionError("Couldn't process your resume right now -- try again in a moment.") from exc

        profile = self.repository.upsert(
            user_id=user_id,
            resume_text=resume_text,
            profile_json=profile_json,
            embedding=embedding,
            embedding_model=settings.gemini_embedding_model,
            source_filename=filename,
        )
        self.repository.record_upload_event(user_id)
        return profile

    def get_profile(self, user_id: int) -> Optional[ResumeProfile]:
        return self.repository.get(user_id)

    def delete(self, user_id: int) -> None:
        self.repository.delete(user_id)
