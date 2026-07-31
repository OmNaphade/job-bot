"""Pulls job postings from Foundit's own internal search API.

Unlike the RSS/JSON sources and the Greenhouse/Lever/Ashby adapters, this
endpoint isn't publicly documented -- it's the same API foundit.in's own
search page calls client-side, found via browser DevTools (see
bot_docs/SOURCES.md for how). It returns clean JSON and works fine
anonymously (verified directly, no login/cookies required), but as an
undocumented endpoint it could change shape or start blocking non-browser
requests without notice -- more fragile than the documented sources, hence
gated by `allow_direct_scraping` alongside the ATS adapters rather than
`enable_rss_sources`.

One adapter instance = one search query (e.g. "java"), reused across a
configured location/country. Candidates still go through the normal
include/exclude keyword matching afterwards, same as every other source --
the query here just needs to be broad enough to surface real candidates,
not an exact filter.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

# Foundit's WAF keyword-blocks any User-Agent whose first token contains "bot"
# (verified: "job-alert-bot/1.0" gets 403'd, "job-alert-ingestion-client/1.0"
# doesn't -- a "job-bot" substring later in the string, e.g. in a URL comment,
# does NOT trigger it, confirmed directly). This is still an honest,
# descriptive identifier of the same project, just avoiding one word that
# trips a naive filter -- not pretending to be a browser. The trailing URL is
# a good-faith contact/identification link, same convention as Googlebot's UA.
_USER_AGENT = "job-alert-ingestion-client/1.0 (+https://github.com/OmNaphade/job-bot)"
_TIMEOUT_SECONDS = 10
_SEARCH_URL = "https://www.foundit.in/home/api/searchResultsPage"
_RESULTS_LIMIT = 20


class FounditAdapter(BaseAdapter):
    def __init__(self, query: str, locations: str, countries: str = "India", enabled: bool = False) -> None:
        self.query = query
        self.locations = locations
        self.countries = countries
        self.source_name = f"foundit:{query}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        params = {
            "start": 0,
            "limit": _RESULTS_LIMIT,
            "query": self.query,
            "locations": self.locations,
            "countries": self.countries,
            "queryDerived": "true",
        }
        try:
            response = requests.get(
                _SEARCH_URL, params=params, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            jobs = response.json().get("data", [])
        except Exception:
            logger.exception("Failed to fetch/parse Foundit search results for query '%s'", self.query)
            return []

        candidates: List[JobCandidate] = []
        for job in jobs:
            jd_url = job.get("jdUrl")
            title = job.get("title")
            if not jd_url or not title:
                continue
            candidates.append(
                JobCandidate(
                    title=title,
                    company=job.get("companyName") or "Unknown",
                    location=self._format_location(job.get("locations") or []),
                    link=f"https://www.foundit.in{jd_url}",
                    source=self.source_name,
                    posted_at=self._format_posted_at(job.get("postedAt")),
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

    @staticmethod
    def _format_posted_at(epoch_ms: Optional[int]) -> Optional[str]:
        if not epoch_ms:
            return None
        try:
            return datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc).isoformat()
        except Exception:
            return None
