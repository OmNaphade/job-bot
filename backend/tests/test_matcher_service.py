from app.ingestion.models import JobCandidate, KeywordConfig
from app.ingestion.services.matcher_service import MatcherService


def _candidate(title: str, company: str = "Acme", location: str = "Remote") -> JobCandidate:
    return JobCandidate(title=title, company=company, location=location, link="https://example.com/1", source="test")


def test_matches_when_include_keyword_present():
    matcher = MatcherService(KeywordConfig(include_keywords=["backend"], exclude_keywords=[]))
    assert matcher.match(_candidate("Backend Engineer")) is True


def test_does_not_match_without_include_keyword():
    matcher = MatcherService(KeywordConfig(include_keywords=["backend"], exclude_keywords=[]))
    assert matcher.match(_candidate("Frontend Engineer")) is False


def test_exclude_keyword_blocks_an_otherwise_matching_candidate():
    matcher = MatcherService(KeywordConfig(include_keywords=["engineer"], exclude_keywords=["senior"]))
    assert matcher.match(_candidate("Senior Backend Engineer")) is False


def test_matching_is_case_insensitive():
    matcher = MatcherService(KeywordConfig(include_keywords=["Backend"], exclude_keywords=[]))
    assert matcher.match(_candidate("backend engineer")) is True


def test_include_keyword_can_match_via_company_or_location():
    matcher = MatcherService(KeywordConfig(include_keywords=["remote"], exclude_keywords=[]))
    assert matcher.match(_candidate("Engineer", location="Remote")) is True
