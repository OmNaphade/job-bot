import html
from dataclasses import dataclass, field
from datetime import datetime

from .util import canonical_url, fingerprint, infer_experience


@dataclass
class Job:
    title: str
    company: str
    location: str
    link: str
    source: str
    posted_at: datetime | None = None
    # Searchable text that is not shown by default: skills/tags, a description snippet, ...
    extra: str = ""
    # Minimum years of experience the posting asks for, when the source says so.
    min_exp: float | None = None
    max_exp: float | None = None
    salary: str = ""
    # Lowest advertised annual salary in lakh INR (LPA), when the source states one.
    salary_lpa: float | None = None
    score: int = 0
    link_key: str = field(init=False)
    dedup_key: str = field(init=False)

    def __post_init__(self) -> None:
        self.title = " ".join(html.unescape(self.title).split())
        self.company = " ".join(html.unescape(self.company or "").split()) or "Unknown"
        self.location = _clean_location(self.location)
        title_exp = infer_experience(self.title)
        if title_exp[0] is not None:
            self.min_exp, self.max_exp = title_exp  # what the title says beats a vague structured field
        elif self.min_exp is None:
            self.min_exp, self.max_exp = infer_experience("", self.extra)
        self.link = canonical_url(self.link)
        self.link_key = self.link
        self.dedup_key = fingerprint(self.title, self.company, self.location)


def _clean_location(raw: str) -> str:
    """Collapses whitespace and drops repeated parts ("Telangana, Telangana, India")."""
    parts: list[str] = []
    for part in html.unescape(raw or "").split(","):
        part = " ".join(part.split())
        if part and part.lower() not in (p.lower() for p in parts):
            parts.append(part)
    return ", ".join(parts) or "Unknown"
