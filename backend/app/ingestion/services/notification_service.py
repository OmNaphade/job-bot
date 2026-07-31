import logging
from typing import List, Tuple

import requests

from app.core.config import settings
from app.models.job import Job

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4000


class NotificationService:
    def send(self, jobs: List[Job]) -> List[int]:
        """Sends a Telegram digest for `jobs` and returns the ids that were
        actually delivered. A chunk that fails to send stops delivery there --
        jobs already sent in earlier chunks still count as delivered, and jobs
        never reached are left for the caller to retry on a later run (see
        JobRepository.list_unnotified/mark_notified)."""
        if not jobs:
            return []

        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset); skipping %d alert(s)", len(jobs))
            return []

        delivered_ids: List[int] = []
        for batch, message in self._build_digest_messages(jobs):
            if not self._send_message(message):
                break
            delivered_ids.extend(job.id for job in batch if job.id is not None)
        return delivered_ids

    def _build_digest_messages(self, jobs: List[Job]) -> List[Tuple[List[Job], str]]:
        header = f"🔔 {len(jobs)} new job match(es)\n\n"

        batches: List[Tuple[List[Job], str]] = []
        current_jobs: List[Job] = []
        current_text = header
        for job in jobs:
            line = self._format_job(job)
            if len(current_text) + len(line) > MAX_MESSAGE_LENGTH:
                batches.append((current_jobs, current_text))
                current_jobs = []
                current_text = ""
            current_jobs.append(job)
            current_text += line
        if current_jobs:
            batches.append((current_jobs, current_text))
        return batches

    def _format_job(self, job: Job) -> str:
        return (
            f"🔹 {job.title} — {job.company}\n"
            f"📍 {job.location} | via {job.source}\n"
            f"{job.link}\n\n"
        )

    def _send_message(self, text: str) -> bool:
        url = TELEGRAM_API_URL.format(token=settings.telegram_bot_token)
        try:
            response = requests.post(
                url,
                json={
                    "chat_id": settings.telegram_chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException:
            logger.exception("Failed to send Telegram notification")
            return False
