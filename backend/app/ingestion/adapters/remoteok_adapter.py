import logging
from typing import List, Optional

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

# RemoteOK's public JSON API 403s requests sent with no User-Agent at all; a descriptive
# UA identifies this as an automated client (as their API expects) -- it doesn't bypass a
# login wall or render JS the way scraping would.
_USER_AGENT = "job-alert-bot/1.0"


class RemoteOkAdapter(BaseAdapter):
    def __init__(self, api_url: Optional[str], enabled: bool = False) -> None:
        self.api_url = api_url
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        if not self.api_url:
            logger.warning("RemoteOK source is enabled but has no API URL configured; skipping.")
            return []

        try:
            response = requests.get(self.api_url, headers={"User-Agent": _USER_AGENT}, timeout=10)
            response.raise_for_status()
            entries = response.json()
        except Exception:
            logger.exception("Failed to fetch/parse RemoteOK API")
            return []

        candidates: List[JobCandidate] = []
        for entry in entries:
            # The first array element is a legal notice, not a job -- it has no "position"/"url".
            if not isinstance(entry, dict):
                continue
            link = entry.get("url")
            title = entry.get("position")
            if not link or not title:
                continue

            candidates.append(
                JobCandidate(
                    title=title,
                    company=entry.get("company") or "Unknown",
                    location=entry.get("location") or "Remote",
                    link=link,
                    source="remoteok",
                    posted_at=entry.get("date"),
                )
            )
        return candidates
