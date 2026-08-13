from app.ingestion.adapters.adzuna_adapter import AdzunaAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_returns_empty_when_disabled():
    adapter = AdzunaAdapter("python", "app-id", "app-key", enabled=False)
    assert adapter.fetch() == []


def test_fetch_maps_job_fields(monkeypatch):
    payload = {
        "results": [
            {
                "title": "Backend Engineer",
                "company": {"display_name": "Acme Corp"},
                "location": {"display_name": "Pune, India"},
                "redirect_url": "https://adzuna.in/land/ad/123",
                "created": "2026-07-30T17:58:25Z",
            },
            {"title": "Missing redirect_url"},
        ]
    }

    captured = {}

    def _fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(payload)

    monkeypatch.setattr("app.ingestion.adapters.adzuna_adapter.requests.get", _fake_get)

    adapter = AdzunaAdapter("python", "app-id", "app-key", country="in", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Pune, India"
    assert candidate.link == "https://adzuna.in/land/ad/123"
    assert candidate.source == "adzuna:python"
    assert candidate.posted_at == "2026-07-30T17:58:25Z"
    assert captured["url"] == "https://api.adzuna.com/v1/api/jobs/in/search/1"
    assert captured["params"]["app_id"] == "app-id"
    assert captured["params"]["app_key"] == "app-key"
    assert captured["params"]["what"] == "python"


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.adzuna_adapter.requests.get", _fake_get)

    adapter = AdzunaAdapter("python", "app-id", "app-key", enabled=True)
    assert adapter.fetch() == []
