from typing import List

from bs4 import BeautifulSoup

from app.ingestion.models import JobCandidate

# Best-effort selectors calibrated against the well-known structure of LinkedIn/Naukri
# job-alert emails (a block per posting, with an anchor linking to the job view page).
# Not validated against a live sample in this environment -- if postings are missed once
# real alerts start arriving, adjust the URL substring / text-extraction heuristics below.
_LINKEDIN_JOB_URL_MARKERS = ("/jobs/view/", "/comm/jobs/view/")
_NAUKRI_JOB_URL_MARKERS = ("naukri.com/job-listings-", "/jobs/job-listings-")


def parse_linkedin_alert_email(html: str) -> List[JobCandidate]:
    return _extract_candidates(html, url_markers=_LINKEDIN_JOB_URL_MARKERS, source_name="linkedin_alerts")


def parse_naukri_alert_email(html: str) -> List[JobCandidate]:
    return _extract_candidates(html, url_markers=_NAUKRI_JOB_URL_MARKERS, source_name="naukri_alerts")


def _extract_candidates(html: str, url_markers: tuple[str, ...], source_name: str) -> List[JobCandidate]:
    soup = BeautifulSoup(html, "html.parser")
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
