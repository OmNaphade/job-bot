from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class JobCandidate:
    title: str
    company: str
    location: str
    link: str
    source: str
    posted_at: Optional[str] = None


@dataclass(frozen=True)
class KeywordFilter:
    """One include/exclude keyword, optionally scoped to a location.

    Backed by `preferences.keyword` / `preferences.location`: when `location`
    is set, this filter only applies to a candidate whose location also
    matches it (e.g. exclude "manager" only for onsite/"New York" postings,
    or include "python" only for "Remote" ones). `location=None` matches
    regardless of the candidate's location, same as before this existed.
    """

    keyword: str
    location: Optional[str] = None


@dataclass(frozen=True)
class KeywordConfig:
    include_keywords: list[KeywordFilter]
    exclude_keywords: list[KeywordFilter]
