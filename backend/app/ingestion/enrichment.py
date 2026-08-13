"""Company-logo enrichment via Clearbit's free, unauthenticated logo API
(https://clearbit.com/logo -- no key, no auth: GET logo.clearbit.com/<domain>
returns an image, 404s gracefully if the domain isn't recognized).

Only wired up where a source hands back a genuinely verified company domain --
never guessed from a company display name or an ATS board token/slug (e.g.
"notion" is not notion.com), which would produce wrong logos more often than
none. See the "Company logo enrichment" section of bot_docs/SOURCES.md.
"""

from typing import Optional
from urllib.parse import urlparse


def clearbit_logo_url(domain: Optional[str]) -> Optional[str]:
    if not domain:
        return None
    return f"https://logo.clearbit.com/{domain}"


def domain_from_url(url: Optional[str], *, exclude_hosts: frozenset[str] = frozenset()) -> Optional[str]:
    """Extracts a bare hostname from `url` for use as a Clearbit lookup key.

    Returns None if `url` is missing/unparseable, or if its host is one of
    `exclude_hosts` -- e.g. Greenhouse's default `boards.greenhouse.io`, which
    is the ATS's own domain, not the company's, and would just fetch the ATS
    platform's logo instead of the company's.
    """
    if not url:
        return None
    host = urlparse(url).hostname
    if not host:
        return None
    host = host.lower()
    if host in exclude_hosts:
        return None
    return host
