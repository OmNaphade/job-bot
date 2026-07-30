from app.ingestion.adapters.ats_adapters import AshbyAdapter, GreenhouseAdapter, LeverAdapter


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_greenhouse_fetch_returns_empty_when_disabled():
    adapter = GreenhouseAdapter("stripe", enabled=False)
    assert adapter.fetch() == []


def test_greenhouse_fetch_maps_job_fields(monkeypatch):
    payload = {
        "jobs": [
            {
                "title": "Backend Engineer",
                "absolute_url": "https://boards.greenhouse.io/stripe/jobs/123",
                "location": {"name": "Remote"},
                "updated_at": "2026-07-20T00:00:00Z",
            },
            {"title": "Missing link"},
        ]
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.ats_adapters.requests.get",
        lambda url, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = GreenhouseAdapter("stripe", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Backend Engineer"
    assert candidate.company == "stripe"
    assert candidate.location == "Remote"
    assert candidate.link == "https://boards.greenhouse.io/stripe/jobs/123"
    assert candidate.source == "greenhouse:stripe"


def test_greenhouse_fetch_returns_empty_on_request_failure(monkeypatch):
    def _fake_get(url, headers=None, timeout=None):
        raise ConnectionError("boom")

    monkeypatch.setattr("app.ingestion.adapters.ats_adapters.requests.get", _fake_get)

    adapter = GreenhouseAdapter("stripe", enabled=True)
    assert adapter.fetch() == []


def test_lever_fetch_returns_empty_when_disabled():
    adapter = LeverAdapter("acme", enabled=False)
    assert adapter.fetch() == []


def test_lever_fetch_maps_job_fields(monkeypatch):
    payload = [
        {
            "text": "Full Stack Engineer",
            "hostedUrl": "https://jobs.lever.co/acme/123",
            "categories": {"location": "Remote - US"},
            "createdAt": 1785000000000,
        },
        {"text": "Missing link"},
    ]
    monkeypatch.setattr(
        "app.ingestion.adapters.ats_adapters.requests.get",
        lambda url, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = LeverAdapter("acme", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Full Stack Engineer"
    assert candidate.company == "acme"
    assert candidate.location == "Remote - US"
    assert candidate.link == "https://jobs.lever.co/acme/123"
    assert candidate.source == "lever:acme"


def test_ashby_fetch_returns_empty_when_disabled():
    adapter = AshbyAdapter("acme", enabled=False)
    assert adapter.fetch() == []


def test_ashby_fetch_maps_job_fields(monkeypatch):
    payload = {
        "jobs": [
            {
                "title": "Platform Engineer",
                "jobUrl": "https://jobs.ashbyhq.com/acme/123",
                "location": "Remote",
                "publishedAt": "2026-07-20T00:00:00Z",
            },
            {"title": "Missing link"},
        ]
    }
    monkeypatch.setattr(
        "app.ingestion.adapters.ats_adapters.requests.get",
        lambda url, headers=None, timeout=None: _FakeResponse(payload),
    )

    adapter = AshbyAdapter("acme", enabled=True)
    candidates = adapter.fetch()

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Platform Engineer"
    assert candidate.company == "acme"
    assert candidate.location == "Remote"
    assert candidate.link == "https://jobs.ashbyhq.com/acme/123"
    assert candidate.source == "ashby:acme"
