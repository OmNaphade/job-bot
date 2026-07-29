from app.ingestion.adapters.rss_adapter import RssAdapter


def test_extract_fields_uses_himalayas_company_field():
    adapter = RssAdapter("himalayas", "https://example.com/feed.rss", enabled=True)
    entry = {"himalayasjobs_companyname": "Acme Corp", "region": "Remote"}

    title, company, location = adapter._extract_fields(entry, "Backend Engineer")

    assert (title, company, location) == ("Backend Engineer", "Acme Corp", "Remote")


def test_extract_fields_splits_company_colon_title_pattern():
    adapter = RssAdapter("weworkremotely", "https://example.com/feed.rss", enabled=True)
    entry = {}

    title, company, location = adapter._extract_fields(entry, "Acme Corp: Backend Engineer")

    assert (title, company) == ("Backend Engineer", "Acme Corp")


def test_extract_fields_falls_back_to_unknown():
    adapter = RssAdapter("generic", "https://example.com/feed.rss", enabled=True)
    entry = {}

    title, company, location = adapter._extract_fields(entry, "Backend Engineer")

    assert (title, company, location) == ("Backend Engineer", "Unknown", "Unknown")


def test_fetch_returns_empty_when_disabled():
    adapter = RssAdapter("unstop", "https://example.com/feed.rss", enabled=False)
    assert adapter.fetch() == []


def test_fetch_returns_empty_and_warns_when_no_feed_url_configured():
    adapter = RssAdapter("unstop", None, enabled=True)
    assert adapter.fetch() == []
