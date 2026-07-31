"""Pulls open job postings from Unstop's own internal listing API.

Like Foundit, this isn't a publicly documented API -- found by testing the
shape of an internal endpoint directly (confirmed live against the real site,
not scraped from HTML). Unlike Foundit, no keyword-blocking was found on the
User-Agent, and no query parameter was found that narrows results
server-side either -- this just fetches the latest open job postings in bulk
and relies on the normal include/exclude keyword matching afterwards, same
as the RSS sources. Still gated by `allow_direct_scraping`, not
`enable_rss_sources`, since it's an undocumented endpoint that could change
shape or disappear without notice -- see bot_docs/SOURCES.md.
"""

import logging
from typing import List

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = "job-alert-ingestion-client/1.0 (+https://github.com/OmNaphade/job-bot)"
_TIMEOUT_SECONDS = 10
_SEARCH_URL = "https://unstop.com/api/public/opportunity/search-result"
_RESULTS_LIMIT = 50


class UnstopAdapter(BaseAdapter):
    def __init__(self, enabled: bool = False) -> None:
        self.source_name = "unstop"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        params = {
            "opportunity": "jobs",
            "searchType": "jobs",
            "oppstatus": "open",
            "page": 1,
            "per_page": _RESULTS_LIMIT,
        }
        try:
            response = requests.get(
                _SEARCH_URL, params=params, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            jobs = response.json().get("data", {}).get("data", [])
        except Exception:
            logger.exception("Failed to fetch/parse Unstop job listings")
            return []

        candidates: List[JobCandidate] = []
        for job in jobs:
            public_url = job.get("public_url")
            title = job.get("title")
            if not public_url or not title:
                continue
            candidates.append(
                JobCandidate(
                    title=title,
                    company=(job.get("organisation") or {}).get("name") or "Unknown",
                    location=self._format_location(job.get("locations") or []),
                    link=f"https://unstop.com/{public_url}",
                    source=self.source_name,
                    posted_at=job.get("updated_at"),
                )
            )
        return candidates

    @staticmethod
    def _format_location(locations: list) -> str:
        if not locations:
            return "Unknown"
        first = locations[0]
        city, state = first.get("city"), first.get("state")
        return ", ".join(part for part in (city, state) if part) or first.get("country") or "Unknown"
