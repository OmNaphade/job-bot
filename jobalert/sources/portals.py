"""Indian job portals that expose their own JSON search endpoints (undocumented, so they may change)."""

import time

from ..models import Job
from ..util import get, parse_dt
from .base import Source, fetch_many


def _place(locations: list) -> str:
    if not locations:
        return ""
    first = locations[0]
    parts: list[str] = []
    for part in (first.get("city"), first.get("state"), first.get("country")):
        if part and part not in parts:
            parts.append(part)
    return ", ".join(parts)


def _lpa(amount) -> str:
    return f"{amount / 100000:g}" if amount else ""


class Foundit(Source):
    """foundit.in (ex-Monster India). One request per query; returns experience and salary ranges."""

    name = "foundit"
    geo_targeted = True

    def __init__(self, config: dict) -> None:
        self.queries = config.get("queries") or []
        self.locations = config.get("locations", "India")
        self.limit = int(config.get("limit", 40))
        self.min_interval_minutes = int(config.get("min_interval_minutes", 60))

    def fetch(self) -> list[Job]:
        return fetch_many(self.queries, self._query, "foundit")

    def _query(self, query: str) -> list[Job]:
        if query is not self.queries[0]:
            time.sleep(0.5)
        params = {
            "start": 0, "limit": self.limit, "query": query, "locations": self.locations,
            "countries": "India", "queryDerived": "true",
        }
        data = get(
            "https://www.foundit.in/home/api/searchResultsPage", params=params, headers={"User-Agent": "job-alert/2.0"}
        ).json()
        jobs = []
        for item in data.get("data", []):
            if not item.get("jdUrl") or not item.get("title"):
                continue
            low = (item.get("minimumSalary") or {}).get("absoluteValue")
            high = (item.get("maximumSalary") or {}).get("absoluteValue")
            shown = bool(low and high) and str(item.get("hideSalary")) != "1"
            salary = f"₹{_lpa(low)}-{_lpa(high)} LPA" if shown else ""
            skills = [s.get("text", "") for s in item.get("itSkills") or [] if isinstance(s, dict)]
            jobs.append(
                Job(
                    title=item["title"],
                    company=item.get("companyName") or (item.get("company") or {}).get("name", ""),
                    location=_place(item.get("locations") or []),
                    link=f"https://www.foundit.in{item['jdUrl']}",
                    source=self.name,
                    posted_at=parse_dt(item.get("postedAt")),
                    extra=" ".join(skills),
                    min_exp=(item.get("minimumExperience") or {}).get("years"),
                    max_exp=(item.get("maximumExperience") or {}).get("years"),
                    salary=salary,
                    salary_lpa=low / 100000 if shown else None,
                )
            )
        return jobs


class Unstop(Source):
    """unstop.com jobs and internships, strong for freshers. No server-side keyword search."""

    name = "unstop"

    def __init__(self, config: dict) -> None:
        self.limit = int(config.get("limit", 50))

    def fetch(self) -> list[Job]:
        params = {"opportunity": "jobs", "searchType": "jobs", "oppstatus": "open", "page": 1, "per_page": self.limit}
        data = get("https://unstop.com/api/public/opportunity/search-result", params=params).json()
        jobs = []
        for item in (data.get("data") or {}).get("data", []):
            if not item.get("public_url") or not item.get("title"):
                continue
            skills = [s.get("skill_name") or s.get("skill", "") for s in item.get("required_skills") or []]
            jobs.append(
                Job(
                    title=item["title"],
                    company=(item.get("organisation") or {}).get("name", ""),
                    location=_place(item.get("locations") or []) or item.get("region", ""),
                    link=f"https://unstop.com/{item['public_url']}",
                    source=self.name,
                    posted_at=parse_dt(item.get("approved_date") or item.get("updated_at")),
                    extra=" ".join(s for s in skills if s),
                )
            )
        return jobs
