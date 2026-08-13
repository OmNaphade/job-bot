"""Pulls job postings from Jooble's public job-search API.

Documented, apiKey-based aggregator API: https://jooble.org/api/about.
One adapter instance = one search query, same "one adapter per query" shape
as AdzunaAdapter/FounditAdapter. Unlike Adzuna, Jooble's endpoint is a POST
with the key embedded in the URL path rather than a query param.
"""

import logging
from typing import List, Optional

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = "job-alert-bot/1.0 (+https://github.com/OmNaphade/job-bot)"
_TIMEOUT_SECONDS = 10


class JoobleAdapter(BaseAdapter):
    def __init__(self, query: str, api_key: str, location: Optional[str] = None, enabled: bool = False) -> None:
        self.query = query
        self.api_key = api_key
        self.location = location
        self.source_name = f"jooble:{query}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        url = f"https://jooble.org/api/{self.api_key}"
        body = {"keywords": self.query}
        if self.location:
            body["location"] = self.location
        try:
            response = requests.post(
                url, json=body, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            jobs = response.json().get("jobs", [])
        except Exception:
            logger.exception("Failed to fetch/parse Jooble results for query '%s'", self.query)
            return []

        candidates: List[JobCandidate] = []
        for job in jobs:
            link = job.get("link")
            title = job.get("title")
            if not link or not title:
                continue

            candidates.append(
                JobCandidate(
                    title=title,
                    company=job.get("company") or "Unknown",
                    location=job.get("location") or "Unknown",
                    link=link,
                    source=self.source_name,
                    posted_at=job.get("updated"),
                )
            )
        return candidates
