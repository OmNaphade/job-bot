from app.ingestion.adapters.remoteok_adapter import RemoteOkAdapter


def test_fetch_returns_empty_when_disabled():
    adapter = RemoteOkAdapter("https://remoteok.com/api", enabled=False)
    assert adapter.fetch() == []


def test_fetch_returns_empty_and_warns_when_no_api_url_configured():
    adapter = RemoteOkAdapter(None, enabled=True)
    assert adapter.fetch() == []


def test_fetch_skips_legal_notice_and_maps_job_fields(monkeypatch):
    payload = [
        {"legal": "https://remoteok.com/terms"},
        {
            "position": "Backend Engineer",
            "company": "Acme Corp",
            "location": "Worldwide",
            "url": "https://remoteok.com/remote-jobs/123",
            "date": "2026-07-20T00:00:00+00:00",
        },
    ]

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    def _fake_get(url, headers=None, timeout=None):
        assert "User-Agent" in headers
        return _FakeResponse()

    monkeypatch.setattr("app.ingestion.adapters.remoteok_adapter.requests.get", _fake_get)

    adapter = RemoteOkAdapter("https://remoteok.com/api", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Worldwide"
    assert candidate.link == "https://remoteok.com/remote-jobs/123"
    assert candidate.source == "remoteok"
    assert candidate.logo_url is None


def test_fetch_passes_through_company_logo_when_present(monkeypatch):
    payload = [
        {
            "position": "Backend Engineer",
            "company": "Acme Corp",
            "location": "Worldwide",
            "url": "https://remoteok.com/remote-jobs/123",
            "company_logo": "https://remoteok.com/assets/logos/acme.png",
        }
    ]

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    monkeypatch.setattr(
        "app.ingestion.adapters.remoteok_adapter.requests.get",
        lambda url, headers=None, timeout=None: _FakeResponse(),
    )

    adapter = RemoteOkAdapter("https://remoteok.com/api", enabled=True)
    candidates = adapter.fetch()

    assert candidates[0].logo_url == "https://remoteok.com/assets/logos/acme.png"


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.remoteok_adapter.requests.get", _fake_get)

    adapter = RemoteOkAdapter("https://remoteok.com/api", enabled=True)
    assert adapter.fetch() == []
