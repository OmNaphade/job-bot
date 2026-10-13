"""Documented, free-key job-search APIs: Adzuna and Jooble."""

from ..models import Job
from ..util import get, parse_dt
from .base import Source, fetch_many


class Adzuna(Source):
    """developer.adzuna.com. One request per query; `country` is a 2-letter code ("in" for India)."""

    name = "adzuna"
    geo_targeted = True

    def __init__(self, config: dict, app_id: str, app_key: str) -> None:
        self.queries = config.get("queries") or []
        self.country = config.get("country", "in")
        self.where = config.get("where", "")
        self.app_id, self.app_key = app_id, app_key

    def fetch(self) -> list[Job]:
        return fetch_many(self.queries, self._query, "adzuna")

    def _query(self, query: str) -> list[Job]:
        params = {
            "app_id": self.app_id, "app_key": self.app_key, "what": query, "results_per_page": 50,
            "sort_by": "date", "max_days_old": 3,
        }
        if self.where:
            params["where"] = self.where
        data = get(f"https://api.adzuna.com/v1/api/jobs/{self.country}/search/1", params=params).json()
        return [
            Job(
                title=item["title"],
                company=(item.get("company") or {}).get("display_name", ""),
                location=(item.get("location") or {}).get("display_name", ""),
                link=item["redirect_url"],
                source=self.name,
                posted_at=parse_dt(item.get("created")),
                extra=item.get("description", ""),
            )
            for item in data.get("results", [])
            if item.get("title") and item.get("redirect_url")
        ]


class Jooble(Source):
    """jooble.org/api/about. One POST per query."""

    name = "jooble"
    geo_targeted = True

    def __init__(self, config: dict, api_key: str) -> None:
        self.queries = config.get("queries") or []
        self.location = config.get("location", "")
        self.api_key = api_key

    def fetch(self) -> list[Job]:
        return fetch_many(self.queries, self._query, "jooble")

    def _query(self, query: str) -> list[Job]:
        body = {"keywords": query, "location": self.location}
        data = get(f"https://jooble.org/api/{self.api_key}", method="POST", json=body).json()
        return [
            Job(
                title=item["title"],
                company=item.get("company", ""),
                location=item.get("location", ""),
                link=item["link"],
                source=self.name,
                posted_at=parse_dt(item.get("updated")),
                extra=item.get("snippet", ""),
                salary=item.get("salary", ""),
            )
            for item in data.get("jobs", [])
            if item.get("title") and item.get("link")
        ]
