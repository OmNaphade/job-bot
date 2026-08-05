import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router
from app.core import security


class _FakeSettings:
    def __init__(self, api_key):
        self.api_key = api_key


@pytest.fixture
def client_with_key(tmp_db, monkeypatch):
    monkeypatch.setattr(security, "settings", _FakeSettings("secret123"))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_stays_open_when_api_key_configured(client_with_key):
    assert client_with_key.get("/health").status_code == 200


def test_protected_route_rejects_missing_key(client_with_key):
    assert client_with_key.get("/jobs").status_code == 401


def test_protected_route_rejects_wrong_key(client_with_key):
    response = client_with_key.get("/jobs", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_protected_route_accepts_correct_key(client_with_key):
    response = client_with_key.get("/jobs", headers={"X-API-Key": "secret123"})
    assert response.status_code == 200


def test_auth_disabled_when_api_key_unset(tmp_db, monkeypatch):
    monkeypatch.setattr(security, "settings", _FakeSettings(None))
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    assert client.get("/jobs").status_code == 200
