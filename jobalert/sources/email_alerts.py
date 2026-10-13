"""LinkedIn / Naukri / Indeed jobs via the saved-search alert emails those sites send you.

This is the dependable route for the big three: you create a job alert on each site (it is a
normal feature of the logged-in site), the site emails you matches, and this reads that inbox over
IMAP. No scraping, no captchas, no blocked IPs. Mail is only read, never changed or marked as seen.
Re-reading the last few days every run is cheap, and the job dedup makes repeats harmless.

Parsers for LinkedIn and Indeed were calibrated against real digest emails. Naukri's is best-effort
(it keys off naukri.com/job-listings-* links); if it misses jobs, send me one of its emails.
"""

import email
import email.message
import imaplib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..models import Job
from ..util import FetchError, parse_dt
from .base import Source
from .linkedin import read_linkedin_job_page

log = logging.getLogger(__name__)

Parser = Callable[[str], list[Job]]


# --------------------------------------------------------------------------- parsers

def _lines(tag) -> list[str]:
    return [line.strip() for line in tag.get_text("\n", strip=True).split("\n") if line.strip()]


def parse_linkedin(html: str) -> list[Job]:
    """Each card is ONE anchor: line 0 = title, line 1 = "Company · Location"."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, Job] = {}
    for anchor in soup.find_all("a", href=True):
        match = re.search(r"/(?:comm/)?jobs/view/(\d+)", anchor["href"])
        if not match or match.group(1) in jobs:
            continue
        lines = _lines(anchor)
        if len(lines) < 2:
            continue  # icon-only anchor wrapping a job we'll see again with text
        company, _, location = lines[1].partition(" · ")
        job_id = match.group(1)
        jobs[job_id] = Job(
            title=lines[0], company=company, location=location,
            link=f"https://www.linkedin.com/jobs/view/{job_id}", source="linkedin_alerts",
        )
    return list(jobs.values())


_INDEED_KEY = re.compile(r"[?&]jk=([0-9a-f]+)")


def parse_indeed(html: str) -> list[Job]:
    """Each card is a table holding a title anchor (href carries jk=<job key>) then company/location lines."""
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, Job] = {}
    for anchor in soup.find_all("a", href=True):
        match = _INDEED_KEY.search(anchor["href"])
        title = anchor.get_text(strip=True)
        if not match or not title or match.group(1) in jobs:
            continue
        card = anchor.find_parent("table", class_="width-100") or anchor.parent
        rest = [line for line in _lines(card) if line != title]
        host = urlparse(anchor["href"]).netloc or "www.indeed.com"
        jobs[match.group(1)] = Job(
            title=title,
            company=rest[0] if rest else "",
            location=rest[1] if len(rest) > 1 else "",
            link=f"https://{host}/viewjob?jk={match.group(1)}",
            source="indeed_alerts",
        )
    return list(jobs.values())


_NAUKRI_MARKERS = ("naukri.com/job-listings-", "/jobs/job-listings-")


def parse_naukri(html: str) -> list[Job]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: dict[str, Job] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        title = anchor.get_text(strip=True)
        if not title or href in jobs or not any(marker in href for marker in _NAUKRI_MARKERS):
            continue
        container = anchor.find_parent(["td", "div", "li", "table"]) or anchor.parent
        rest = [line for line in _lines(container) if line != title] if container else []
        jobs[href] = Job(
            title=title,
            company=rest[0] if rest else "",
            location=rest[1] if len(rest) > 1 else "",
            link=href,
            source="naukri_alerts",
        )
    return list(jobs.values())


PARSERS: dict[str, Parser] = {"linkedin": parse_linkedin, "naukri": parse_naukri, "indeed": parse_indeed}
_DEFAULT_SENDERS = {
    "linkedin": "jobalerts-noreply@linkedin.com",
    "naukri": "naukri.com",
    "indeed": "jobalert.indeed.com",
}


# --------------------------------------------------------------------------- IMAP

class EmailAlerts(Source):
    """One instance reads every configured provider over a single IMAP connection."""

    name = "email_alerts"
    geo_targeted = True  # your own saved searches already chose the place
    needs_detail = True  # LinkedIn alert emails link to real job pages; we read them like search results

    def wants_detail(self, job: Job) -> bool:
        return "linkedin.com/jobs/view/" in job.link

    def enrich(self, job: Job) -> None:
        read_linkedin_job_page(job)

    def __init__(self, config: dict, address: str, password: str) -> None:
        self.address, self.password = address, password
        self.host = config.get("imap_host", "imap.gmail.com")
        self.port = int(config.get("imap_port", 993))
        self.lookback_days = int(config.get("lookback_days", 3))
        self.providers = {
            name: {
                "sender": (config.get(name) or {}).get("sender") or _DEFAULT_SENDERS[name],
                "mailboxes": (config.get(name) or {}).get("mailboxes") or ["INBOX"],
            }
            for name in PARSERS
            if (config.get(name) or {}).get("enabled", True)
        }

    def fetch(self) -> list[Job]:
        try:
            connection = imaplib.IMAP4_SSL(self.host, self.port)
            connection.login(self.address, self.password)
        except (imaplib.IMAP4.error, OSError) as exc:
            raise FetchError(f"email_alerts: IMAP login failed ({type(exc).__name__}: {exc})") from exc

        jobs: list[Job] = []
        try:
            for provider, settings in self.providers.items():
                for mailbox in settings["mailboxes"]:
                    jobs.extend(self._read_mailbox(connection, provider, settings["sender"], mailbox))
        finally:
            try:
                connection.logout()
            except (imaplib.IMAP4.error, OSError):
                pass
        return jobs

    def _read_mailbox(self, connection: imaplib.IMAP4_SSL, provider: str, sender: str, mailbox: str) -> list[Job]:
        status, _ = connection.select(f'"{mailbox}"', readonly=True)
        if status != "OK":
            log.info("email_alerts: mailbox '%s' not found, skipping (create the Gmail label or remove it)", mailbox)
            return []
        since = (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).strftime("%d-%b-%Y")
        status, data = connection.search(None, "SINCE", since, "FROM", f'"{sender}"')
        if status != "OK" or not data or not data[0]:
            return []

        jobs: list[Job] = []
        for number in data[0].split():
            status, parts = connection.fetch(number, "(BODY.PEEK[])")
            if status != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            message = email.message_from_bytes(parts[0][1])
            html = _html_body(message)
            if not html:
                continue
            received = parse_dt(message.get("Date"))
            try:
                parsed = PARSERS[provider](html)
            except Exception:  # a layout change in one provider must not break the others
                log.exception("email_alerts: could not parse a %s email", provider)
                continue
            if not parsed:
                log.warning("email_alerts: no jobs recognised in a %s email (subject: %.60s); its layout may "
                            "have changed", provider, message.get("Subject", ""))
            for job in parsed:
                job.posted_at = received  # alert emails carry no per-job date; the email date is close enough
            jobs.extend(parsed)
        return jobs


def _html_body(message: email.message.Message) -> Optional[str]:
    for part in message.walk():
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return None
