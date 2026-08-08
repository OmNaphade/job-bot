import re
from typing import List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.ingestion.models import JobCandidate

_HTML_PARSER = "html.parser"

# Naukri: best-effort, calibrated against the well-known *shape* of alert-digest
# emails, not a validated live sample -- none of the sender's messages seen so far
# were actual job digests (all were marketing/newsletter content), so there was
# nothing real to check this against yet. If postings are missed once a genuine
# saved-search digest arrives, adjust the URL substring / text heuristics below.
_NAUKRI_JOB_URL_MARKERS = ("naukri.com/job-listings-", "/jobs/job-listings-")

# Foundit: NOT currently usable. A real alert email was inspected directly, and its
# "Apply Now" links go through an authenticated redirect
# (foundit.in/rio/autoLogin/seeker/<token>) rather than a plain foundit.in/job/<slug>
# URL -- so there is no stable per-job URL to key off in the email body at all. This
# channel needs a different extraction strategy (e.g. pulling title/company text
# near each "Apply Now" button) before it can work; left unimplemented since
# FounditAdapter's direct API integration already covers Foundit without this
# problem. See bot_docs/SOURCES.md.


def parse_linkedin_alert_email(html: str) -> List[JobCandidate]:
    """Calibrated directly against a real LinkedIn job-alert-digest email.

    Each job's entire card (title, "Company (middle dot) Location", then a
    trailing social-proof/status line -- "N company alumni", "Actively
    recruiting", "Apply", etc., confirmed to vary a lot) sits inside ONE anchor
    as three-plus text lines with no HTML separator between them, so
    `get_text(strip=True)` alone smashes them together. Splitting on newlines
    from `get_text("\\n", ...)` and taking lines by fixed position (title is
    always line 0, "Company (dot) Location" is always line 1) is far more
    reliable than trying to pattern-match the open-ended set of trailing noise
    lines. Real hrefs also carry heavy per-email tracking query strings
    (trackingId/refId/lipi/...) that would produce a different `link` for the
    same job across separate digest emails and break dedup (`jobs.link
    UNIQUE`) -- the job ID is extracted and used to build a clean, stable
    permalink instead of using the raw href.
    """
    soup = BeautifulSoup(html, _HTML_PARSER)
    candidates: dict[str, JobCandidate] = {}

    for anchor in soup.find_all("a", href=True):
        match = re.search(r"/(?:comm/)?jobs/view/(\d+)", anchor["href"])
        if not match:
            continue
        job_id = match.group(1)
        if job_id in candidates:
            continue

        lines = [line.strip() for line in anchor.get_text("\n", strip=True).split("\n") if line.strip()]
        if len(lines) < 2:
            continue  # icon-only anchor wrapping the same job, no text to extract

        title = lines[0]
        company, _, location = lines[1].partition(" · ")
        candidates[job_id] = JobCandidate(
            title=title,
            company=company.strip() or "Unknown",
            location=location.strip() or "Unknown",
            link=f"https://www.linkedin.com/jobs/view/{job_id}/",
            source="linkedin_alerts",
        )

    return list(candidates.values())


def parse_naukri_alert_email(html: str) -> List[JobCandidate]:
    return _extract_candidates(html, url_markers=_NAUKRI_JOB_URL_MARKERS, source_name="naukri_alerts")


# Indeed: calibrated directly against a real Indeed job-alert-digest email. Each
# job card is a <table class="width-100"> box containing a title anchor (href
# carries a `jk=<job key>` query param -- Indeed's stable per-posting identifier,
# same redirect-link problem LinkedIn's parser already solves) followed by two
# plain-text company/location lines within the same card. The `jk` value is used
# to build a clean canonical `/viewjob?jk=<key>` link (and to dedupe) instead of
# trusting the raw href, which carries heavy per-email tracking query params
# (tk/alid/bb/qd/rd) that would otherwise defeat `jobs.link UNIQUE` dedup across
# separate digest emails for the same posting.
_INDEED_JOB_ID_PATTERN = re.compile(r"[?&]jk=([0-9a-f]+)")


def parse_indeed_alert_email(html: str) -> List[JobCandidate]:
    soup = BeautifulSoup(html, _HTML_PARSER)
    candidates: dict[str, JobCandidate] = {}

    for anchor in soup.find_all("a", href=True):
        match = _INDEED_JOB_ID_PATTERN.search(anchor["href"])
        if not match:
            continue
        job_id = match.group(1)
        if job_id in candidates:
            continue

        title = anchor.get_text(strip=True)
        if not title:
            continue

        card = anchor.find_parent("table", class_="width-100") or anchor.parent
        lines = [line.strip() for line in card.get_text("\n", strip=True).split("\n") if line.strip()]
        remaining = [line for line in lines if line != title]
        company = remaining[0] if len(remaining) >= 1 else "Unknown"
        location = remaining[1] if len(remaining) >= 2 else "Unknown"

        host = urlparse(anchor["href"]).netloc or "www.indeed.com"
        candidates[job_id] = JobCandidate(
            title=title,
            company=company,
            location=location,
            link=f"https://{host}/viewjob?jk={job_id}",
            source="indeed_alerts",
        )

    return list(candidates.values())


def _extract_candidates(html: str, url_markers: tuple[str, ...], source_name: str) -> List[JobCandidate]:
    soup = BeautifulSoup(html, _HTML_PARSER)
    candidates: dict[str, JobCandidate] = {}

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not any(marker in href for marker in url_markers):
            continue

        title = anchor.get_text(strip=True)
        if not title:
            continue

        if href in candidates:
            continue

        company, location = _guess_company_and_location(anchor, title)
        candidates[href] = JobCandidate(
            title=title,
            company=company,
            location=location,
            link=href,
            source=source_name,
        )

    return list(candidates.values())


def _guess_company_and_location(anchor, title: str) -> tuple[str, str]:
    container = anchor.find_parent(["td", "div", "li", "table"]) or anchor.parent
    if container is None:
        return "Unknown", "Unknown"

    lines = [line.strip() for line in container.get_text("\n", strip=True).split("\n") if line.strip()]
    remaining = [line for line in lines if line != title]

    company = remaining[0] if len(remaining) >= 1 else "Unknown"
    location = remaining[1] if len(remaining) >= 2 else "Unknown"
    return company, location
