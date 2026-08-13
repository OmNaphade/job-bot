from app.ingestion.adapters.jooble_adapter import JoobleAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_returns_empty_when_disabled():
    adapter = JoobleAdapter("python", "api-key", enabled=False)
    assert adapter.fetch() == []


def test_fetch_maps_job_fields(monkeypatch):
    payload = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "company": "Acme Corp",
                "location": "Pune, India",
                "link": "https://jooble.org/desc/123",
                "updated": "2026-07-30T17:58:25Z",
            },
            {"company": "Missing link"},
        ]
    }

    captured = {}

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = json
        return _FakeResponse(payload)

    monkeypatch.setattr("app.ingestion.adapters.jooble_adapter.requests.post", _fake_post)

    adapter = JoobleAdapter("python", "api-key", location="Pune", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Pune, India"
    assert candidate.link == "https://jooble.org/desc/123"
    assert candidate.source == "jooble:python"
    assert candidate.posted_at == "2026-07-30T17:58:25Z"
    assert captured["url"] == "https://jooble.org/api/api-key"
    assert captured["body"] == {"keywords": "python", "location": "Pune"}


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_post(url, json=None, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.jooble_adapter.requests.post", _fake_post)

    adapter = JoobleAdapter("python", "api-key", enabled=True)
    assert adapter.fetch() == []
