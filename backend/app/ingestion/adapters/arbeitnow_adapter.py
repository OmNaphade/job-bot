"""Pulls job postings from Arbeitnow's public job-board API.

Fully public, documented, no auth or API key required:
https://arbeitnow.com/api/job-board-api -- meant for exactly this kind of
consumption, same trust tier as the RSS/JSON sources. Skews toward remote
and visa-sponsorship-friendly roles.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

_API_URL = "https://arbeitnow.com/api/job-board-api"
_TIMEOUT_SECONDS = 10
_USER_AGENT = "job-alert-bot/1.0 (+https://github.com/OmNaphade/job-bot)"


class ArbeitnowAdapter(BaseAdapter):
    def __init__(self, enabled: bool = False) -> None:
        self.source_name = "arbeitnow"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        try:
            response = requests.get(_API_URL, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            entries = response.json().get("data", [])
        except Exception:
            logger.exception("Failed to fetch/parse Arbeitnow job board API")
            return []

        candidates: List[JobCandidate] = []
        for entry in entries:
            link = entry.get("url")
            title = entry.get("title")
            if not link or not title:
                continue

            candidates.append(
                JobCandidate(
                    title=title,
                    company=entry.get("company_name") or "Unknown",
                    location=self._format_location(entry),
                    link=link,
                    source=self.source_name,
                    posted_at=self._format_posted_at(entry.get("created_at")),
                )
            )
        return candidates

    @staticmethod
    def _format_location(entry: dict) -> str:
        location = entry.get("location")
        if location:
            return location
        return "Remote" if entry.get("remote") else "Unknown"

    @staticmethod
    def _format_posted_at(epoch_seconds: Optional[int]) -> Optional[str]:
        if not epoch_seconds:
            return None
        try:
            return datetime.fromtimestamp(epoch_seconds, tz=timezone.utc).isoformat()
        except Exception:
            return None
