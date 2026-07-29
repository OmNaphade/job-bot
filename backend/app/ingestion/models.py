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
class KeywordConfig:
    include_keywords: list[str]
    exclude_keywords: list[str]
