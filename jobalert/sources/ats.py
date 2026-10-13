"""Jobs straight from company career pages through their applicant-tracking-system public JSON APIs.

Greenhouse, Lever and Ashby each publish a per-company job-board API meant for embedding listings
on a careers page. Postings usually show up here before they spread to the big job boards, which
makes this the fastest way to hear about a role. Find a company's token in its careers URL:
boards.greenhouse.io/<token>, jobs.lever.co/<slug>, jobs.ashbyhq.com/<name>.
"""

from ..models import Job
from ..util import get, parse_dt
from .base import Source


class Greenhouse(Source):
    def __init__(self, token: str) -> None:
        self.token = token
        self.name = f"greenhouse:{token}"

    def fetch(self) -> list[Job]:
        data = get(f"https://boards-api.greenhouse.io/v1/boards/{self.token}/jobs").json()
        return [
            Job(
                title=item["title"],
                company=item.get("company_name") or self.token,
                location=(item.get("location") or {}).get("name", ""),
                link=item["absolute_url"],
                source=self.name,
                posted_at=parse_dt(item.get("first_published") or item.get("updated_at")),
            )
            for item in data.get("jobs", [])
            if item.get("title") and item.get("absolute_url")
        ]


class Lever(Source):
    def __init__(self, slug: str) -> None:
        self.slug = slug
        self.name = f"lever:{slug}"

    def fetch(self) -> list[Job]:
        data = get(f"https://api.lever.co/v0/postings/{self.slug}", params={"mode": "json"}).json()
        return [
            Job(
                title=item["text"],
                company=self.slug,
                location=(item.get("categories") or {}).get("location", ""),
                link=item["hostedUrl"],
                source=self.name,
                posted_at=parse_dt(item.get("createdAt")),
                extra=(item.get("categories") or {}).get("team", ""),
            )
            for item in data
            if item.get("text") and item.get("hostedUrl")
        ]


class Ashby(Source):
    def __init__(self, board: str) -> None:
        self.board = board
        self.name = f"ashby:{board}"

    def fetch(self) -> list[Job]:
        data = get(f"https://api.ashbyhq.com/posting-api/job-board/{self.board}").json()
        return [
            Job(
                title=item["title"],
                company=self.board,
                location=item.get("location", ""),
                link=item.get("jobUrl") or item["applyUrl"],
                source=self.name,
                posted_at=parse_dt(item.get("publishedAt")),
                extra=item.get("department", ""),
            )
            for item in data.get("jobs", [])
            if item.get("title") and (item.get("jobUrl") or item.get("applyUrl"))
        ]


def build(config: dict) -> list[Source]:
    sources: list[Source] = []
    sources += [Greenhouse(t) for t in config.get("greenhouse", [])]
    sources += [Lever(s) for s in config.get("lever", [])]
    sources += [Ashby(b) for b in config.get("ashby", [])]
    return sources
