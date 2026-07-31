"""Adapters that pull job postings directly from a company's applicant-tracking
system (ATS), rather than an aggregator feed. Greenhouse, Lever, and Ashby each
publish a public per-company JSON API meant for embedding job listings on the
company's own careers page -- consuming it is not scraping (no HTML parsing, no
login wall, no JS rendering), but it is direct-from-company-site, so all three
are gated by the `allow_direct_scraping` ingestion setting rather than
`enable_rss_sources`.

One adapter instance = one company's board, identified by the token/slug found
in that company's careers page URL (e.g. https://boards.greenhouse.io/stripe
-> board token "stripe"). The registry builds one instance per token listed in
the matching env var (see safe_registry.py).
"""

import logging
from typing import List

import requests

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)

_USER_AGENT = "job-alert-bot/1.0 (+https://github.com/OmNaphade/job-bot)"
_TIMEOUT_SECONDS = 10


class GreenhouseAdapter(BaseAdapter):
    def __init__(self, board_token: str, enabled: bool = False) -> None:
        self.board_token = board_token
        self.source_name = f"greenhouse:{board_token}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        url = f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs"
        try:
            response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            jobs = response.json().get("jobs", [])
        except Exception:
            logger.exception("Failed to fetch/parse Greenhouse board '%s'", self.board_token)
            return []

        candidates: List[JobCandidate] = []
        for job in jobs:
            link = job.get("absolute_url")
            title = job.get("title")
            if not link or not title:
                continue
            location = (job.get("location") or {}).get("name") or "Unknown"
            candidates.append(
                JobCandidate(
                    title=title,
                    company=self.board_token,
                    location=location,
                    link=link,
                    source=self.source_name,
                    posted_at=job.get("updated_at"),
                )
            )
        return candidates


class LeverAdapter(BaseAdapter):
    def __init__(self, company_slug: str, enabled: bool = False) -> None:
        self.company_slug = company_slug
        self.source_name = f"lever:{company_slug}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        url = f"https://api.lever.co/v0/postings/{self.company_slug}?mode=json"
        try:
            response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            postings = response.json()
        except Exception:
            logger.exception("Failed to fetch/parse Lever postings for '%s'", self.company_slug)
            return []

        candidates: List[JobCandidate] = []
        for posting in postings:
            link = posting.get("hostedUrl")
            title = posting.get("text")
            if not link or not title:
                continue
            location = (posting.get("categories") or {}).get("location") or "Unknown"
            candidates.append(
                JobCandidate(
                    title=title,
                    company=self.company_slug,
                    location=location,
                    link=link,
                    source=self.source_name,
                    posted_at=posting.get("createdAt"),
                )
            )
        return candidates


class AshbyAdapter(BaseAdapter):
    def __init__(self, board_name: str, enabled: bool = False) -> None:
        self.board_name = board_name
        self.source_name = f"ashby:{board_name}"
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.board_name}"
        try:
            response = requests.get(url, headers={"User-Agent": _USER_AGENT}, timeout=_TIMEOUT_SECONDS)
            response.raise_for_status()
            jobs = response.json().get("jobs", [])
        except Exception:
            logger.exception("Failed to fetch/parse Ashby board '%s'", self.board_name)
            return []

        candidates: List[JobCandidate] = []
        for job in jobs:
            link = job.get("jobUrl") or job.get("applyUrl")
            title = job.get("title")
            if not link or not title:
                continue
            candidates.append(
                JobCandidate(
                    title=title,
                    company=self.board_name,
                    location=job.get("location") or "Unknown",
                    link=link,
                    source=self.source_name,
                    posted_at=job.get("publishedAt"),
                )
            )
        return candidates
