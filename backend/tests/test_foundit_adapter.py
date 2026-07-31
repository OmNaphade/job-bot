from app.ingestion.adapters.foundit_adapter import FounditAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_returns_empty_when_disabled():
    adapter = FounditAdapter("java", "pune", enabled=False)
    assert adapter.fetch() == []


def test_fetch_maps_job_fields(monkeypatch):
    payload = {
        "data": [
            {
                "title": "Backend Engineer",
                "companyName": "Acme Corp",
                "jdUrl": "/job/backend-engineer-acme-corp-pune-123",
                "locations": [{"city": "Pune", "state": "Maharashtra", "country": "India"}],
                "postedAt": 1785434305000,
            },
            {"title": "Missing jdUrl"},
        ]
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.foundit_adapter.requests.get",
        lambda url, params=None, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = FounditAdapter("java", "pune", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Pune, Maharashtra"
    assert candidate.link == "https://www.foundit.in/job/backend-engineer-acme-corp-pune-123"
    assert candidate.source == "foundit:java"
    assert candidate.posted_at == "2026-07-30T17:58:25+00:00"


def test_fetch_falls_back_to_country_when_no_city(monkeypatch):
    payload = {
        "data": [
            {
                "title": "Remote Engineer",
                "companyName": "Acme Corp",
                "jdUrl": "/job/remote-engineer-acme-corp-456",
                "locations": [{"country": "India"}],
            }
        ]
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.foundit_adapter.requests.get",
        lambda url, params=None, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = FounditAdapter("python", "pune", enabled=True)
    candidates = adapter.fetch()

    assert candidates[0].location == "India"
    assert candidates[0].posted_at is None


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.foundit_adapter.requests.get", _fake_get)

    adapter = FounditAdapter("java", "pune", enabled=True)
    assert adapter.fetch() == []
