"""LinkedIn job search through the public "guest" endpoint the logged-out jobs pages use.

No login and no account involved, but it is an unofficial endpoint: LinkedIn rate-limits it hard
(and blocks most cloud/datacenter IPs, including GitHub Actions' runners at times). From a home
connection it works well; if it gets blocked the run just reports the source as failed and the
email-alert source below remains the dependable way to get LinkedIn jobs.
"""

import logging
import random
import re
import time

from bs4 import BeautifulSoup

from ..models import Job
from ..util import FetchError, get, infer_required_experience, parse_dt
from .base import Source, fetch_many

log = logging.getLogger(__name__)

_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
_MAX_DESCRIPTION = 6000
_SENIOR_LEVELS = ("mid-senior", "director", "executive")
_PAGE_SIZE = 25
_EXPERIENCE = {"internship": 1, "entry": 2, "associate": 3, "mid_senior": 4, "director": 5, "executive": 6}
_WORK_TYPE = {"onsite": 1, "remote": 2, "hybrid": 3}


class LinkedIn(Source):
    name = "linkedin"
    geo_targeted = True

    def __init__(self, config: dict) -> None:
        self.searches = config.get("searches") or []
        self.hours = int(config.get("posted_within_hours", 24))
        self.pages = max(1, int(config.get("pages", 1)))
        self.experience = [_EXPERIENCE[e] for e in config.get("experience", []) if e in _EXPERIENCE]
        self.work_type = [_WORK_TYPE[w] for w in config.get("work_type", []) if w in _WORK_TYPE]
        self.min_interval_minutes = int(config.get("min_interval_minutes", 60))
        self._first_request = True
        self._blocked_searches = 0
        # Search results only carry title/company/location. Opening each new job's page gives its
        # description, so experience and tech stack can actually be checked. Without it, results are
        # trusted as relevant because you wrote the search.
        self.needs_detail = bool(config.get("fetch_details", True))
        self.prefiltered = not self.needs_detail

    def fetch(self) -> list[Job]:
        return fetch_many(self.searches, self._search, "linkedin")

    def _search(self, search: dict) -> list[Job]:
        if self._blocked_searches >= 2:
            # Two searches in a row were refused even after waiting: LinkedIn is blocking this IP.
            # Hammering it with the remaining searches only wastes minutes (and a GitHub runner's quota).
            raise FetchError("linkedin: skipped, still rate-limited from earlier searches")
        jobs: list[Job] = []
        for page in range(self.pages):
            params = {
                "keywords": search["keywords"],
                "location": search.get("location", ""),
                "f_TPR": f"r{self.hours * 3600}",
                "sortBy": "DD",
                "start": page * _PAGE_SIZE,
            }
            if self.experience:
                params["f_E"] = ",".join(map(str, self.experience))
            if self.work_type:
                params["f_WT"] = ",".join(map(str, self.work_type))

            if not self._first_request:
                time.sleep(random.uniform(3.0, 5.0))  # be polite; LinkedIn throttles bursts
            self._first_request = False
            try:
                response = get(_URL, params=params, retries=2, backoff=10)  # 429s clear after ~10-30s
            except FetchError:
                if page == 0:
                    self._blocked_searches += 1
                    raise
                break  # a later page being throttled shouldn't discard page 1
            self._blocked_searches = 0
            page_jobs = parse_cards(response.text)
            jobs.extend(page_jobs)
            if len(page_jobs) < _PAGE_SIZE:
                break
        return jobs


    def enrich(self, job: Job) -> None:
        read_linkedin_job_page(job)


def read_linkedin_job_page(job: Job) -> None:
    """Opens a LinkedIn job's public page and fills in its description and required experience."""
    time.sleep(random.uniform(2.0, 4.0))
    job_id = job.link.rsplit("/", 1)[-1]
    response = get(_DETAIL_URL.format(id=job_id), retries=1, backoff=10)
    description, seniority = parse_detail(response.text)
    if not description:
        raise FetchError(f"linkedin: no description found for job {job_id}")
    job.extra = description
    if job.min_exp is None:
        job.min_exp, job.max_exp = infer_required_experience(description)
    if job.min_exp is None and seniority.lower().startswith(_SENIOR_LEVELS):
        job.min_exp = 5  # LinkedIn's own seniority label, used only when the text states no years


def parse_detail(markup: str) -> tuple[str, str]:
    """(description text, LinkedIn's "Seniority level" label) from a job detail page."""
    soup = BeautifulSoup(markup, "html.parser")
    body = soup.select_one(".show-more-less-html__markup")
    description = body.get_text("\n", strip=True)[:_MAX_DESCRIPTION] if body else ""
    seniority = ""
    for item in soup.select("li.description__job-criteria-item"):
        header = item.select_one(".description__job-criteria-subheader")
        value = item.select_one(".description__job-criteria-text")
        if header and value and header.get_text(strip=True).lower().startswith("seniority"):
            seniority = value.get_text(strip=True)
    return description, seniority


def parse_cards(markup: str) -> list[Job]:
    soup = BeautifulSoup(markup, "html.parser")
    jobs: list[Job] = []
    for card in soup.select("div.base-search-card, div.job-search-card"):
        urn = card.get("data-entity-urn", "")
        match = re.search(r"(\d+)$", urn)
        title = card.select_one(".base-search-card__title")
        if not match or not title:
            continue
        company = card.select_one(".base-search-card__subtitle")
        location = card.select_one(".job-search-card__location")
        posted = card.select_one("time")
        jobs.append(
            Job(
                title=title.get_text(strip=True),
                company=company.get_text(strip=True) if company else "",
                location=location.get_text(strip=True) if location else "",
                link=f"https://www.linkedin.com/jobs/view/{match.group(1)}",
                source="linkedin",
                posted_at=parse_dt(posted.get("datetime")) if posted else None,
            )
        )
    return jobs
