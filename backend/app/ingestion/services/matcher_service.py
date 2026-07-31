import re
from typing import List, Pattern

from app.ingestion.models import JobCandidate, KeywordConfig, KeywordFilter


def _keyword_pattern(keyword: str) -> Pattern[str]:
    # \b enforces whole-word/phrase matching so "go" doesn't match "Google" and
    # "lead" doesn't match "leadership" -- plain substring matching (the previous
    # behavior) let short keywords silently match unrelated words.
    return re.compile(rf"\b{re.escape(keyword.strip())}\b", re.IGNORECASE)


class _CompiledFilter:
    def __init__(self, keyword_filter: KeywordFilter) -> None:
        self.pattern = _keyword_pattern(keyword_filter.keyword)
        self.location = keyword_filter.location


class MatcherService:
    def __init__(self, keyword_config: KeywordConfig | None = None) -> None:
        config = keyword_config or KeywordConfig(
            include_keywords=[KeywordFilter(k) for k in ("backend", "flutter", "python", "developer")],
            exclude_keywords=[KeywordFilter(k) for k in ("senior", "manager", "lead")],
        )
        self.include_keywords = config.include_keywords
        self.exclude_keywords = config.exclude_keywords
        self._include_filters = [_CompiledFilter(f) for f in self.include_keywords if f.keyword.strip()]
        self._exclude_filters = [_CompiledFilter(f) for f in self.exclude_keywords if f.keyword.strip()]

    def match(self, candidate: JobCandidate) -> bool:
        text = f"{candidate.title} {candidate.company} {candidate.location}"
        if not any(self._filter_applies(f, candidate, text) for f in self._include_filters):
            return False
        if any(self._filter_applies(f, candidate, text) for f in self._exclude_filters):
            return False
        return True

    @staticmethod
    def _filter_applies(compiled: _CompiledFilter, candidate: JobCandidate, text: str) -> bool:
        if not compiled.pattern.search(text):
            return False
        if compiled.location and compiled.location.strip().lower() not in candidate.location.lower():
            return False
        return True
