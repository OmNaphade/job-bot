from app.ingestion.adapters.unstop_adapter import UnstopAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_returns_empty_when_disabled():
    adapter = UnstopAdapter(enabled=False)
    assert adapter.fetch() == []


def test_fetch_maps_job_fields(monkeypatch):
    payload = {
        "data": {
            "data": [
                {
                    "title": "Backend Engineer",
                    "public_url": "jobs/backend-engineer-acme-corp-123",
                    "organisation": {"name": "Acme Corp"},
                    "locations": [{"city": "Bangalore", "state": "Karnataka", "country": "India"}],
                    "updated_at": "2026-07-30T21:43:54+05:30",
                },
                {"title": "Missing public_url"},
            ]
        }
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.unstop_adapter.requests.get",
        lambda url, params=None, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = UnstopAdapter(enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Bangalore, Karnataka"
    assert candidate.link == "https://unstop.com/jobs/backend-engineer-acme-corp-123"
    assert candidate.source == "unstop"
    assert candidate.posted_at == "2026-07-30T21:43:54+05:30"


def test_fetch_falls_back_to_country_when_no_city(monkeypatch):
    payload = {
        "data": {
            "data": [
                {
                    "title": "Remote Engineer",
                    "public_url": "jobs/remote-engineer-456",
                    "organisation": {"name": "Acme Corp"},
                    "locations": [{"country": "India"}],
                }
            ]
        }
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.unstop_adapter.requests.get",
        lambda url, params=None, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = UnstopAdapter(enabled=True)
    candidates = adapter.fetch()

    assert candidates[0].location == "India"


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, params=None, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.unstop_adapter.requests.get", _fake_get)

    adapter = UnstopAdapter(enabled=True)
    assert adapter.fetch() == []
