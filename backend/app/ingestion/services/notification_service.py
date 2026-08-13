import logging
from abc import ABC, abstractmethod
from typing import List, Tuple

import requests

from app.models.job import Job
from app.models.notification_settings import NotificationSettings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
MAX_MESSAGE_LENGTH = 4000
# Discord's hard message-length cap (lower than Telegram's) -- digests to
# Discord are chunked against this instead of MAX_MESSAGE_LENGTH.
DISCORD_MAX_MESSAGE_LENGTH = 2000


class NotificationChannel(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        raise NotImplementedError

    @property
    @abstractmethod
    def chunk_limit(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def send_text(self, text: str) -> bool:
        raise NotImplementedError


class TelegramChannel(NotificationChannel):
    name = "telegram"

    def __init__(self, settings: NotificationSettings) -> None:
        self.settings = settings

    @property
    def chunk_limit(self) -> int:
        return MAX_MESSAGE_LENGTH

    def is_configured(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    def send_text(self, text: str) -> bool:
        url = TELEGRAM_API_URL.format(token=self.settings.telegram_bot_token)
        try:
            response = requests.post(
                url,
                json={
                    "chat_id": self.settings.telegram_chat_id,
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


class SlackChannel(NotificationChannel):
    name = "slack"

    def __init__(self, settings: NotificationSettings) -> None:
        self.settings = settings

    @property
    def chunk_limit(self) -> int:
        return MAX_MESSAGE_LENGTH

    def is_configured(self) -> bool:
        return bool(self.settings.slack_webhook_url)

    def send_text(self, text: str) -> bool:
        try:
            response = requests.post(self.settings.slack_webhook_url, json={"text": text}, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException:
            logger.exception("Failed to send Slack notification")
            return False


class DiscordChannel(NotificationChannel):
    name = "discord"

    def __init__(self, settings: NotificationSettings) -> None:
        self.settings = settings

    @property
    def chunk_limit(self) -> int:
        return DISCORD_MAX_MESSAGE_LENGTH

    def is_configured(self) -> bool:
        return bool(self.settings.discord_webhook_url)

    def send_text(self, text: str) -> bool:
        try:
            response = requests.post(self.settings.discord_webhook_url, json={"content": text}, timeout=10)
            response.raise_for_status()
            return True
        except requests.RequestException:
            logger.exception("Failed to send Discord notification")
            return False


class NotificationService:
    def __init__(
        self, settings: NotificationSettings | None = None, channels: List[NotificationChannel] | None = None
    ) -> None:
        if channels is not None:
            self._channels = channels
        else:
            settings = settings or NotificationSettings()
            self._channels = [TelegramChannel(settings), SlackChannel(settings), DiscordChannel(settings)]

    def send(self, jobs: List[Job]) -> List[int]:
        """Sends a digest for `jobs` to every configured channel and returns the
        ids that were delivered to at least one of them. Each channel chunks and
        delivers independently -- one channel's failure (or being unconfigured)
        never blocks another, and a job is only left pending for retry
        (JobRepository.list_unnotified/mark_notified) if every configured
        channel failed to deliver it."""
        if not jobs:
            return []

        configured = [channel for channel in self._channels if channel.is_configured()]
        if not configured:
            logger.warning(
                "No notification channel configured (Telegram/Slack/Discord all unset); skipping %d alert(s)",
                len(jobs),
            )
            return []

        delivered_ids: set[int] = set()
        for channel in configured:
            delivered_ids.update(self._send_to_channel(channel, jobs))
        return sorted(delivered_ids)

    def _send_to_channel(self, channel: NotificationChannel, jobs: List[Job]) -> List[int]:
        delivered: List[int] = []
        for batch, message in self._build_digest_messages(jobs, channel.chunk_limit):
            if not channel.send_text(message):
                break
            delivered.extend(job.id for job in batch if job.id is not None)
        return delivered

    def _build_digest_messages(self, jobs: List[Job], chunk_limit: int) -> List[Tuple[List[Job], str]]:
        header = f"🔔 {len(jobs)} new job match(es)\n\n"

        batches: List[Tuple[List[Job], str]] = []
        current_jobs: List[Job] = []
        current_text = header
        for job in jobs:
            line = self._format_job(job)
            if len(current_text) + len(line) > chunk_limit:
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
