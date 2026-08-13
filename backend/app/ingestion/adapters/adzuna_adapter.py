"""Pulls job postings from Adzuna's public job-search API.

Documented, apiKey-based aggregator API meant for exactly this kind of
consumption: https://developer.adzuna.com/overview. One adapter instance =
one search query, reused across a configured country/app credentials --
same "one adapter per query" shape as FounditAdapter, just against a
documented, officially supported endpoint instead of a reverse-engineered
internal one.
"""

import logging
from typing import List

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = "job-alert-bot/1.0 (+https://github.com/OmNaphade/job-bot)"
_TIMEOUT_SECONDS = 10


class AdzunaAdapter(BaseAdapter):
    def __init__(self, query: str, app_id: str, app_key: str, country: str = "in", enabled: bool = False) -> None:
        self.query = query
        self.app_id = app_id
        self.app_key = app_key
        self.country = country
        self.source_name = f"adzuna:{query}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        url = f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/1"
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "what": self.query,
            "content-type": "application/json",
        }
        try:
            response = requests.get(
                url, params=params, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            results = response.json().get("results", [])
        except Exception:
            logger.exception("Failed to fetch/parse Adzuna results for query '%s'", self.query)
            return []

        candidates: List[JobCandidate] = []
        for result in results:
            link = result.get("redirect_url")
            title = result.get("title")
            if not link or not title:
                continue

            company = (result.get("company") or {}).get("display_name") or "Unknown"
            location = (result.get("location") or {}).get("display_name") or "Unknown"
            candidates.append(
                JobCandidate(
                    title=title,
                    company=company,
                    location=location,
                    link=link,
                    source=self.source_name,
                    posted_at=result.get("created"),
                )
            )
        return candidates
