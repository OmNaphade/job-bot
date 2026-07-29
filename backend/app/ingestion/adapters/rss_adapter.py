import logging
from typing import List, Optional

import feedparser

from app.ingestion.adapters.base_adapter import BaseAdapter
from app.ingestion.models import JobCandidate

logger = logging.getLogger(__name__)


class RssAdapter(BaseAdapter):
    def __init__(self, source_name: str, feed_url: Optional[str], enabled: bool = False) -> None:
        self.source_name = source_name
        self.feed_url = feed_url
        self.enabled = enabled

    def fetch(self) -> List[JobCandidate]:
        if not self.enabled:
            return []

        if not self.feed_url:
            logger.warning(
                "RSS source '%s' is enabled but has no feed URL configured; skipping. "
                "Find the real feed/API endpoint via the portal's search page (DevTools -> Network -> XHR, "
                "or a '?format=rss' link) and set it via the matching env var.",
                self.source_name,
            )
            return []

        try:
            parsed = feedparser.parse(self.feed_url)
        except Exception:
            logger.exception("Failed to fetch/parse RSS feed for source '%s'", self.source_name)
            return []

        if parsed.bozo and not parsed.entries:
            logger.warning("RSS feed for source '%s' could not be parsed: %s", self.source_name, parsed.get("bozo_exception"))
            return []

        candidates: List[JobCandidate] = []
        for entry in parsed.entries:
            link = entry.get("link")
            title = entry.get("title")
            if not link or not title:
                continue

            title, company, location = self._extract_fields(entry, title)
            candidates.append(
                JobCandidate(
                    title=title,
                    company=company,
                    location=location,
                    link=link,
                    source=self.source_name,
                    posted_at=entry.get("published"),
                )
            )
        return candidates

    def _extract_fields(self, entry: dict, title: str) -> tuple[str, str, str]:
        # A handful of known feeds expose structured fields beyond plain RSS; use them when present.
        company = entry.get("himalayasjobs_companyname") or entry.get("author")
        location = entry.get("region")

        # Some feeds (e.g. WeWorkRemotely) put "Company: Role" in the title instead of a separate field.
        if not company and ":" in title:
            possible_company, possible_title = title.split(":", 1)
            if 0 < len(possible_company) <= 60:
                company, title = possible_company.strip(), possible_title.strip()

        return title, company or "Unknown", location or "Unknown"
