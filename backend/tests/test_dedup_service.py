from app.ingestion.models import JobCandidate
from app.ingestion.services.dedup_service import DedupService


def _candidate(link: str, title: str = "Engineer") -> JobCandidate:
    return JobCandidate(title=title, company="Acme", location="Remote", link=link, source="test")


def test_filter_new_removes_duplicate_links_within_a_batch():
    dedup = DedupService()
    candidates = [_candidate("https://example.com/1"), _candidate("https://example.com/1"), _candidate("https://example.com/2")]

    result = dedup.filter_new(candidates)

    assert [c.link for c in result] == ["https://example.com/1", "https://example.com/2"]


def test_filter_new_keeps_order_and_all_unique_links():
    dedup = DedupService()
    candidates = [_candidate(f"https://example.com/{i}") for i in range(5)]

    result = dedup.filter_new(candidates)

    assert result == candidates


def test_filter_new_on_empty_list():
    assert DedupService().filter_new([]) == []
