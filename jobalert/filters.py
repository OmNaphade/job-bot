from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .models import Job
from .sources.base import Source
from .util import word_pattern

_UNKNOWN_LOCATIONS = {"", "unknown", "n/a", "not specified"}
# A posting that names one of these is open to you even if it also names a region you can't work from.
_OPEN_TO_INDIA = [word_pattern(k) for k in ("india", "anywhere", "worldwide", "apac", "asia")]


@dataclass
class Verdict:
    keep: bool
    reason: str = ""


class JobFilter:
    """Decides whether a job is relevant and how well it fits.

    - include: at least one must appear in the title. A title that names no technology is accepted
      only if it matches generic_titles ("Associate Engineer", "Analyst", ...) AND the description or
      skills list shows real tech evidence (min_tech_evidence hits, at least one an include term).
    - companies.exclude drops a company; companies.prefer adds score.
    - location.exclude drops region-locked postings ("US only", "Remote, Mexico") unless they also
      name India/anywhere. run.min_salary_lpa drops jobs advertising less, when a salary is stated.
    - skills: +1 score each (max 5) when they appear in the title/skills text; never required.
    - exclude: any hit in the *title* drops the job (descriptions mention "senior" far too often).
    - location.allow: for sources where you didn't pick the place, the job's location must mention
      one of these; unknown locations pass.
    - run.max_age_days: drop jobs whose posting date is known and older than this.
    - run.max_experience_years: drop jobs asking for more years than you have, when the source says.
    """

    def __init__(self, config: dict) -> None:
        keywords = config.get("keywords", {})
        location = config.get("location", {})
        run = config.get("run", {})
        self.include = [word_pattern(k) for k in keywords.get("include", []) if k.strip()]
        self.exclude = [word_pattern(k) for k in keywords.get("exclude", []) if k.strip()]
        self.boost = [word_pattern(k) for k in keywords.get("boost", []) if k.strip()]
        self.skills = [word_pattern(k) for k in keywords.get("skills", []) if k.strip()]
        companies = config.get("companies", {})
        self.exclude_companies = [word_pattern(k) for k in companies.get("exclude", []) if k.strip()]
        self.prefer_companies = [word_pattern(k) for k in companies.get("prefer", []) if k.strip()]
        self.reject_places = [word_pattern(k) for k in location.get("exclude", []) if k.strip()]
        self.generic_titles = [word_pattern(k) for k in keywords.get("generic_titles", []) if k.strip()]
        self.allow_locations = [word_pattern(k) for k in location.get("allow", []) if k.strip()]
        self.preferred_locations = [word_pattern(k) for k in location.get("preferred", []) if k.strip()]
        self.min_evidence = int(run.get("min_tech_evidence", 2))
        self.max_age = timedelta(days=float(run.get("max_age_days", 3)))
        min_salary = run.get("min_salary_lpa")
        self.min_salary: float | None = float(min_salary) if min_salary is not None else None
        max_exp = run.get("max_experience_years")
        self.max_experience: float | None = float(max_exp) if max_exp is not None else None

    def check(self, job: Job, source: Source, now: datetime | None = None, *, final: bool = True) -> Verdict:
        """`final=False` skips the keyword gate, for sources whose job description hasn't been read yet."""
        now = now or datetime.now(UTC)

        if job.posted_at and now - job.posted_at > self.max_age:
            return Verdict(False, "too old")
        if any(p.search(job.title) for p in self.exclude):
            return Verdict(False, "excluded keyword")
        if any(p.search(job.company) for p in self.exclude_companies):
            return Verdict(False, "excluded company")
        if self.reject_places and not source.geo_targeted:
            where = f"{job.location} {job.title}"
            if any(p.search(where) for p in self.reject_places) and not any(p.search(where) for p in _OPEN_TO_INDIA):
                return Verdict(False, "region-locked")
        if self.min_salary is not None and job.salary_lpa is not None and job.salary_lpa < self.min_salary:
            return Verdict(False, "salary")
        place_matters = bool(self.allow_locations) and not source.geo_targeted
        place_known = job.location.lower() not in _UNKNOWN_LOCATIONS
        if place_matters and place_known and not any(p.search(job.location) for p in self.allow_locations):
            return Verdict(False, "location")
        if self.max_experience is not None and job.min_exp is not None and job.min_exp > self.max_experience:
            return Verdict(False, "experience")
        if not final or source.prefiltered or not self.include:
            return Verdict(True)  # saved-search emails are your own searches, trusted as relevant
        if any(p.search(job.title) for p in self.include):
            return Verdict(True)
        # The title names no technology ("Associate Engineer", "Analyst", ...). Fine for the generic
        # titles you listed, but only if the description/skills prove it is really a tech role.
        if self.generic_titles and not any(p.search(job.title) for p in self.generic_titles):
            return Verdict(False, "no include keyword")
        include_hits = sum(1 for p in self.include if p.search(job.extra))
        skill_hits = sum(1 for p in self.skills if p.search(job.extra))
        if include_hits < 1 or include_hits + skill_hits < self.min_evidence:
            return Verdict(False, "title has no tech keyword, description doesn't prove it")
        return Verdict(True)

    def score(self, job: Job, now: datetime | None = None) -> int:
        """Higher = better fit. Title hits count most; fresh and preferred-city jobs get a bump."""
        now = now or datetime.now(UTC)
        score = 3 * sum(1 for p in self.include if p.search(job.title))
        score += min(4, sum(1 for p in self.include if not p.search(job.title) and p.search(job.extra)))
        score += 2 * sum(1 for p in self.boost if p.search(job.title) or p.search(job.extra))
        # Skills only rank jobs, they never qualify one: "sql" or "git" alone shouldn't make a job relevant.
        score += min(5, sum(1 for p in self.skills if p.search(job.title) or p.search(job.extra)))
        if any(p.search(job.company) for p in self.prefer_companies):
            score += 3
        if any(p.search(job.location) for p in self.preferred_locations):
            score += 2
        if job.posted_at:
            age_hours = (now - job.posted_at).total_seconds() / 3600
            score += 2 if age_hours <= 6 else 1 if age_hours <= 24 else 0
        return score
