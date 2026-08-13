from app.ingestion.adapters.themuse_adapter import TheMuseAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_returns_empty_when_disabled():
    adapter = TheMuseAdapter("Software Engineering", enabled=False)
    assert adapter.fetch() == []


def test_fetch_maps_job_fields(monkeypatch):
    payload = {
        "results": [
            {
                "name": "Backend Engineer",
                "company": {"name": "Acme Corp"},
                "locations": [{"name": "Remote"}],
                "refs": {"landing_page": "https://themuse.com/jobs/acme/backend-engineer"},
                "publication_date": "2026-07-30T17:58:25Z",
            },
            {"company": {"name": "Missing name/link"}},
        ]
    }

    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(payload)

    monkeypatch.setattr("app.ingestion.adapters.themuse_adapter.requests.get", _fake_get)

    adapter = TheMuseAdapter("Software Engineering", api_key="key", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Remote"
    assert candidate.link == "https://themuse.com/jobs/acme/backend-engineer"
    assert candidate.source == "themuse:Software Engineering"
    assert candidate.posted_at == "2026-07-30T17:58:25Z"
    assert captured["params"] == {"category": "Software Engineering", "api_key": "key"}


def test_fetch_works_without_api_key(monkeypatch):
    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse({"results": []})

    monkeypatch.setattr("app.ingestion.adapters.themuse_adapter.requests.get", _fake_get)

    adapter = TheMuseAdapter("Software Engineering", enabled=True)
    assert adapter.fetch() == []
    assert captured["params"] == {"category": "Software Engineering"}


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.themuse_adapter.requests.get", _fake_get)

    adapter = TheMuseAdapter("Software Engineering", enabled=True)
    assert adapter.fetch() == []
