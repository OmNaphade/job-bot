import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT = 20

_TRACKING_PARAMS = {
    "ref", "refid", "trackingid", "trk", "lipi", "source", "src", "tk", "alid", "bb", "qd", "rd",
    "position", "pagenum", "gh_src", "gh_jid_src", "lever-source", "lever-origin", "fbclid", "gclid",
}


class FetchError(Exception):
    """A source could not be fetched at all (not just 'returned zero jobs')."""


def get(url: str, *, params: dict | None = None, headers: dict | None = None, retries: int = 2,
        method: str = "GET", json: Any = None, backoff: float = 2) -> requests.Response:
    """HTTP request with a browser UA and a few retries on 429/5xx (waiting backoff, 2x backoff, ...)."""
    merged = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    merged.update(headers or {})
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, params=params, headers=merged, json=json, timeout=TIMEOUT)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status < 500 and status != 429:
                break  # 4xx other than 429 won't fix itself
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
    raise FetchError(f"{url}: {last}")


def canonical_url(url: str) -> str:
    """Strips tracking params/fragments so the same job gets the same key across emails and feeds."""
    parsed = urlparse(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    ]
    path = parsed.path.rstrip("/") or parsed.path
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", urlencode(query), ""))


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def fingerprint(title: str, company: str, location: str) -> str:
    """Same role at the same company in the same city, whichever site it came from."""
    city = _alnum(location).split(" ")[0] if _alnum(location) else ""
    return f"{_alnum(title)}|{_alnum(company)}|{city}"


def parse_dt(value: Any) -> datetime | None:
    """Best-effort parse of ISO strings, RFC 2822 dates and epoch seconds/milliseconds."""
    if value in (None, "", 0):
        return None
    try:
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
            number = float(value)
            if number > 1e11:  # milliseconds
                number /= 1000
            return datetime.fromtimestamp(number, tz=UTC)
        text = str(value).strip()
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            parsed = parsedate_to_datetime(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except (ValueError, TypeError, OverflowError):
        return None


_EXP_RANGE = re.compile(r"(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?![A-Za-z])", re.IGNORECASE)
_EXP_MIN = re.compile(r"(\d{1,2})\s*\+\s*(?:years?|yrs?)(?![A-Za-z])", re.IGNORECASE)


def infer_experience(title: str, extra: str = "") -> tuple[float | None, float | None]:
    """Reads "2-4 yrs" / "3+ years" out of text for sources that don't give experience as a field.

    A bare "N+ years" is trusted only in the title: descriptions say "10+ years of excellence"
    about the company far more often than about the candidate. Ranges are trusted in both.
    """
    for text in (title, extra):
        match = _EXP_RANGE.search(text)
        if match:
            low, high = float(match.group(1)), float(match.group(2))
            if low <= high <= 40:
                return low, high
    match = _EXP_MIN.search(title)
    if match:
        return float(match.group(1)), None
    return None, None


_YEARS = re.compile(r"(\d{1,2})\s*(?:(?:-|–|to)\s*(\d{1,2}))?\s*(\+)?\s*(?:years?|yrs?)(?![A-Za-z])", re.IGNORECASE)
_BOAST = re.compile(r"(?:with|over|more than|past|last|since|for)\s*$", re.IGNORECASE)


def infer_required_experience(text: str) -> tuple[float | None, float | None]:
    """Reads the experience a job *asks for* out of a long description.

    Takes the first "N years"/"N-M years"/"N+ years" that sits next to the word "experience" and is
    not a company boast ("with 20 years of experience in payments"). Numbers above 12 are ignored for
    the same reason. Returns (None, None) when nothing convincing is found.
    """
    for match in _YEARS.finditer(text):
        low = float(match.group(1))
        high = float(match.group(2)) if match.group(2) else None
        if low > 12 or (high is not None and (high < low or high > 40)):
            continue
        before = text[max(0, match.start() - 40):match.start()]
        after = text[match.end():match.end() + 40]
        if "experience" not in before.lower() and "experience" not in after.lower():
            continue
        if _BOAST.search(before.rstrip()):
            continue
        return low, high
    return None, None


def word_pattern(term: str) -> re.Pattern:
    """Whole-word, case-insensitive match so 'go' doesn't hit 'Google' and 'lead' doesn't hit 'leadership'."""
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term.strip())}(?![A-Za-z0-9])", re.IGNORECASE)
