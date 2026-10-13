"""Public remote-job feeds. No keys, no login; all are meant to be consumed this way."""

import feedparser

from ..models import Job
from ..util import FetchError, get, parse_dt
from .base import Source

RSS_FEEDS = {
    "weworkremotely": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "himalayas": "https://himalayas.app/jobs/rss",
    "jobspresso": "https://jobspresso.co/feed/",
    "nodesk": "https://nodesk.co/remote-jobs/index.xml",
}


class RssBoard(Source):
    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url

    def fetch(self) -> list[Job]:
        parsed = feedparser.parse(get(self.url).content)
        if parsed.bozo and not parsed.entries:
            raise FetchError(f"{self.name}: feed could not be parsed")
        jobs = []
        for entry in parsed.entries:
            title, link = entry.get("title"), entry.get("link")
            if not title or not link:
                continue
            company = entry.get("himalayasjobs_companyname") or entry.get("author") or ""
            # WeWorkRemotely puts "Company: Role" in the title.
            if not company and ":" in title:
                head, tail = title.split(":", 1)
                if 0 < len(head) <= 60:
                    company, title = head.strip(), tail.strip()
            jobs.append(
                Job(
                    title=title,
                    company=company,
                    location=entry.get("region") or "Remote",
                    link=link,
                    source=self.name,
                    posted_at=parse_dt(entry.get("published")),
                    extra=" ".join(tag.get("term", "") for tag in entry.get("tags", [])),
                )
            )
        return jobs


class RemoteOk(Source):
    name = "remoteok"

    def fetch(self) -> list[Job]:
        data = get("https://remoteok.com/api").json()
        jobs = []
        for entry in data:
            # The first element is a legal notice, not a job.
            if not isinstance(entry, dict) or not entry.get("position") or not entry.get("url"):
                continue
            jobs.append(
                Job(
                    title=entry["position"],
                    company=entry.get("company", ""),
                    location=entry.get("location") or "Remote",
                    link=entry["url"],
                    source=self.name,
                    posted_at=parse_dt(entry.get("date")),
                    extra=" ".join(entry.get("tags", [])),
                )
            )
        return jobs


class Remotive(Source):
    name = "remotive"

    def fetch(self) -> list[Job]:
        data = get("https://remotive.com/api/remote-jobs", params={"category": "software-dev"}).json()
        return [
            Job(
                title=entry["title"],
                company=entry.get("company_name", ""),
                location=entry.get("candidate_required_location") or "Remote",
                link=entry["url"],
                source=self.name,
                posted_at=parse_dt(entry.get("publication_date")),
                extra=" ".join(entry.get("tags", [])),
                salary=entry.get("salary", ""),
            )
            for entry in data.get("jobs", [])
            if entry.get("title") and entry.get("url")
        ]


class Arbeitnow(Source):
    name = "arbeitnow"

    def fetch(self) -> list[Job]:
        data = get("https://www.arbeitnow.com/api/job-board-api").json()
        return [
            Job(
                title=entry["title"],
                company=entry.get("company_name", ""),
                location=entry.get("location") or ("Remote" if entry.get("remote") else ""),
                link=entry["url"],
                source=self.name,
                posted_at=parse_dt(entry.get("created_at")),
                extra=" ".join(entry.get("tags", [])),
            )
            for entry in data.get("data", [])
            if entry.get("title") and entry.get("url")
        ]


def build(config: dict) -> list[Source]:
    enabled = config.get("boards")
    names = set(enabled) if enabled else {*RSS_FEEDS, "remoteok", "remotive", "arbeitnow"}
    sources: list[Source] = [RssBoard(n, u) for n, u in RSS_FEEDS.items() if n in names]
    sources += [cls() for cls in (RemoteOk, Remotive, Arbeitnow) if cls.name in names]
    return sources
