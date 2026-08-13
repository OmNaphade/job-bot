"""Pulls job postings from The Muse's public jobs API.

Documented API: https://www.themuse.com/developers/api/v2. Works
unauthenticated at low volume; an API key is optional and only raises the
rate limit. One adapter instance = one job category (e.g. "Software
Engineering"), same "one adapter per query" shape as the other keyed
aggregators.
"""

import logging
from typing import List, Optional

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = "job-alert-bot/1.0 (+https://github.com/OmNaphade/job-bot)"
_TIMEOUT_SECONDS = 10
_API_URL = "https://www.themuse.com/api/public/jobs"


class TheMuseAdapter(BaseAdapter):
    def __init__(self, category: str, api_key: Optional[str] = None, enabled: bool = False) -> None:
        self.category = category
        self.api_key = api_key
        self.source_name = f"themuse:{category}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        params = {"category": self.category}
        if self.api_key:
            params["api_key"] = self.api_key
        try:
            response = requests.get(
                _API_URL, params=params, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        except Exception:
            logger.exception("Failed to fetch/parse The Muse results for category '%s'", self.category)
            return []

        candidates: List[JobCandidate] = []
        for result in results:
            link = (result.get("refs") or {}).get("landing_page")
            title = result.get("name")
            if not link or not title:
                continue

            company = (result.get("company") or {}).get("name") or "Unknown"
            locations = result.get("locations") or []
            location = locations[0].get("name") if locations else "Unknown"
            candidates.append(
                JobCandidate(
                    title=title,
                    company=company,
                    location=location or "Unknown",
                    link=link,
                    source=self.source_name,
                    posted_at=result.get("publication_date"),
                )
            )
        return candidates
