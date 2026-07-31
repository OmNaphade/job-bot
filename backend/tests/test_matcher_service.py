from app.ingestion.models import JobCandidate, KeywordConfig, KeywordFilter
from app.ingestion.services.matcher_service import MatcherService


def _candidate(title: str, company: str = "Acme", location: str = "Remote") -> JobCandidate:
    return JobCandidate(title=title, company=company, location=location, link="https://example.com/1", source="test")


def _config(include: list, exclude: list) -> KeywordConfig:
    return KeywordConfig(
        include_keywords=[f if isinstance(f, KeywordFilter) else KeywordFilter(f) for f in include],
        exclude_keywords=[f if isinstance(f, KeywordFilter) else KeywordFilter(f) for f in exclude],
    )


def test_matches_when_include_keyword_present():
    matcher = MatcherService(_config(["backend"], []))
    assert matcher.match(_candidate("Backend Engineer")) is True


def test_does_not_match_without_include_keyword():
    matcher = MatcherService(_config(["backend"], []))
    assert matcher.match(_candidate("Frontend Engineer")) is False


def test_exclude_keyword_blocks_an_otherwise_matching_candidate():
    matcher = MatcherService(_config(["engineer"], ["senior"]))
    assert matcher.match(_candidate("Senior Backend Engineer")) is False


def test_matching_is_case_insensitive():
    matcher = MatcherService(_config(["Backend"], []))
    assert matcher.match(_candidate("backend engineer")) is True


def test_include_keyword_can_match_via_company_or_location():
    matcher = MatcherService(_config(["remote"], []))
    assert matcher.match(_candidate("Engineer", location="Remote")) is True


def test_short_keyword_does_not_match_inside_a_longer_word():
    # Previously plain substring matching -- "go" would match "Google" and
    # "java" would match "JavaScript". Word-boundary matching fixes both.
    matcher = MatcherService(_config(["go"], []))
    assert matcher.match(_candidate("Software Engineer", company="Google")) is False


def test_exclude_keyword_does_not_block_via_a_longer_containing_word():
    matcher = MatcherService(_config(["engineer"], ["lead"]))
    assert matcher.match(_candidate("Backend Engineer, Team Leadership Program")) is True


def test_whole_word_keyword_still_matches_as_its_own_word():
    matcher = MatcherService(_config(["lead"], []))
    assert matcher.match(_candidate("Tech Lead")) is True


def test_location_scoped_include_keyword_requires_matching_location():
    matcher = MatcherService(_config([KeywordFilter("python", location="India")], []))
    assert matcher.match(_candidate("Python Developer", location="India")) is True
    assert matcher.match(_candidate("Python Developer", location="Remote")) is False


def test_location_scoped_exclude_keyword_only_blocks_matching_location():
    matcher = MatcherService(_config(["manager"], [KeywordFilter("manager", location="New York")]))
    assert matcher.match(_candidate("Engineering Manager", location="New York")) is False
    assert matcher.match(_candidate("Engineering Manager", location="Remote")) is True
