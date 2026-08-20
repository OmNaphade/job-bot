import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import matching_routes
from app.api.routes import router
from app.models.match import JobMatch


class _FakeMatchingService:
    def __init__(self, matches: list[JobMatch] | None = None):
        self.matches = matches or []
        self.calls: list[tuple] = []

    def get_matches(self, user_id, limit=20, offset=0):
        self.calls.append((user_id, limit, offset))
        return self.matches


def _match(id_: int, score: float) -> JobMatch:
    return JobMatch(
        id=id_,
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        link=f"https://x.com/{id_}",
        source="rss",
        match_score=score,
    )


@pytest.fixture
def fake_matching_service():
    return _FakeMatchingService()


@pytest.fixture
def client(tmp_db, fake_matching_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[matching_routes.get_matching_service] = lambda: fake_matching_service
    return TestClient(app)


def test_list_matches_returns_ranked_jobs(client, auth_headers, fake_matching_service):
    fake_matching_service.matches = [_match(1, 0.95), _match(2, 0.5)]

    response = client.get("/matches", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert [m["id"] for m in body] == [1, 2]
    assert body[0]["match_score"] == 0.95


def test_list_matches_returns_empty_list_without_a_resume(client, auth_headers):
    response = client.get("/matches", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_list_matches_passes_through_limit_and_offset(client, auth_headers, fake_matching_service):
    client.get("/matches?limit=5&offset=10", headers=auth_headers)

    assert fake_matching_service.calls[-1][1:] == (5, 10)


def test_list_matches_requires_auth(client):
    assert client.get("/matches").status_code == 401
