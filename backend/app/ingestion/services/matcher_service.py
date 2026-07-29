from typing import List

from app.ingestion.models import JobCandidate, KeywordConfig


class MatcherService:
    def __init__(self, keyword_config: KeywordConfig | None = None) -> None:
        config = keyword_config or KeywordConfig(
            include_keywords=["backend", "flutter", "python", "developer"],
            exclude_keywords=["senior", "manager", "lead"],
        )
        self.include_keywords = config.include_keywords
        self.exclude_keywords = config.exclude_keywords

    def match(self, candidate: JobCandidate) -> bool:
        text = f"{candidate.title} {candidate.company} {candidate.location}".lower()
        if not any(keyword.lower() in text for keyword in self.include_keywords):
            return False
        if any(keyword.lower() in text for keyword in self.exclude_keywords):
            return False
        return True
