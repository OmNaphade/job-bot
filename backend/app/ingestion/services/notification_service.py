import logging
from typing import List

import requests

from app.core.config import settings
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4000


class NotificationService:
    def send(self, candidates: List[JobCandidate]) -> int:
        if not candidates:
            return 0

        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset); skipping %d alert(s)", len(candidates))
            return 0

        for message in self._build_digest_messages(candidates):
            if not self._send_message(message):
                return 0

        return len(candidates)

    def _build_digest_messages(self, candidates: List[JobCandidate]) -> List[str]:
        lines = [self._format_candidate(candidate) for candidate in candidates]
        header = f"🔔 {len(candidates)} new job match(es)\n\n"

        messages: List[str] = []
        current = header
        for line in lines:
            if len(current) + len(line) > MAX_MESSAGE_LENGTH:
                messages.append(current)
                current = ""
            current += line
        if current:
            messages.append(current)
        return messages

    def _format_candidate(self, candidate: JobCandidate) -> str:
        return (
            f"🔹 {candidate.title} — {candidate.company}\n"
            f"📍 {candidate.location} | via {candidate.source}\n"
            f"{candidate.link}\n\n"
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
