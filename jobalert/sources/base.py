import logging
from collections.abc import Callable, Iterable

from ..models import Job
from ..util import FetchError

log = logging.getLogger(__name__)


class Source:
    """One place jobs come from. `fetch` returns candidates or raises FetchError if the source is down."""

    name: str = "source"
    # True when results are trusted as relevant without a keyword check. Only used by LinkedIn when
    # fetch_details is off; saved-search emails are NOT trusted (alerts are often broad).
    prefiltered: bool = False
    # True when you already chose the place (LinkedIn location, Foundit locations, ...), so the
    # location.allow list shouldn't second-guess it. Untargeted sources (remote boards, company
    # boards, Unstop, Telegram channels) are checked against location.allow.
    geo_targeted: bool = False
    # True when search results are thin (title/company only) and each new job's page should be
    # opened to read its description before deciding. See `enrich`.
    needs_detail: bool = False
    # Minimum minutes between two fetches of this source (0 = every run). Keeps request volume low for
    # sites that don't welcome automated access, however often the scheduler fires.
    min_interval_minutes: int = 0

    def wants_detail(self, job: Job) -> bool:
        """Whether this particular job's page can be read (a source may support only some of its jobs)."""
        return self.needs_detail

    def enrich(self, job: Job) -> None:
        """Fills in job.extra / experience from the job's own page. Raises FetchError on failure."""
        raise NotImplementedError

    def fetch(self) -> list[Job]:
        raise NotImplementedError


def fetch_many(requests_: Iterable, run: Callable[[object], list[Job] | None], label: str) -> list[Job]:
    """Runs `run` once per request, tolerating individual failures.

    Raises FetchError only when *every* request failed, so one bad query doesn't mark the whole
    source as broken but a blocked/down source does.
    """
    jobs: list[Job] = []
    total = failed = 0
    last_error: Exception | None = None
    for item in requests_:
        total += 1
        try:
            jobs.extend(run(item) or [])
        except FetchError as exc:
            failed += 1
            last_error = exc
            log.warning("%s: %s", label, exc)
    if total and failed == total:
        raise FetchError(f"{label}: all {total} request(s) failed ({last_error})")
    return jobs
