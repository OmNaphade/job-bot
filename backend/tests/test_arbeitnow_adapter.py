from app.ingestion.adapters.arbeitnow_adapter import ArbeitnowAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_fetch_returns_empty_when_disabled():
    adapter = ArbeitnowAdapter(enabled=False)
    assert adapter.fetch() == []


def test_fetch_maps_job_fields(monkeypatch):
    payload = {
        "data": [
            {
                "title": "Backend Engineer",
                "company_name": "Acme Corp",
                "location": "Berlin, Germany",
                "url": "https://arbeitnow.com/jobs/backend-engineer-acme-corp",
                "created_at": 1785434305,
                "remote": False,
            },
            {"company_name": "Missing title"},
        ]
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.arbeitnow_adapter.requests.get",
        lambda url, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = ArbeitnowAdapter(enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "Acme Corp"
    assert candidate.location == "Berlin, Germany"
    assert candidate.link == "https://arbeitnow.com/jobs/backend-engineer-acme-corp"
    assert candidate.source == "arbeitnow"
    assert candidate.posted_at == "2026-07-30T17:58:25+00:00"


def test_fetch_falls_back_to_remote_when_no_location(monkeypatch):
    payload = {
        "data": [
            {
                "title": "Remote Engineer",
                "company_name": "Acme Corp",
                "url": "https://arbeitnow.com/jobs/remote-engineer",
                "remote": True,
            }
        ]
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.arbeitnow_adapter.requests.get",
        lambda url, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = ArbeitnowAdapter(enabled=True)
    candidates = adapter.fetch()

    assert candidates[0].location == "Remote"
    assert candidates[0].posted_at is None


def test_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.arbeitnow_adapter.requests.get", _fake_get)

    adapter = ArbeitnowAdapter(enabled=True)
    assert adapter.fetch() == []
