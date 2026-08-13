import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import router


@pytest.fixture
def client(tmp_db):
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_signup_login_and_logout_flow(client):
    signup = client.post("/auth/signup", json={"email": "user@example.com", "password": "password123"})
    assert signup.status_code == 200
    token = signup.json()["token"]
    assert signup.json()["user"]["email"] == "user@example.com"

    # Session from signup already works.
    assert client.get("/jobs", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    login = client.post("/auth/login", json={"email": "user@example.com", "password": "password123"})
    assert login.status_code == 200
    login_token = login.json()["token"]

    logout = client.post("/auth/logout", headers={"Authorization": f"Bearer {login_token}"})
    assert logout.status_code == 200
    assert client.get("/jobs", headers={"Authorization": f"Bearer {login_token}"}).status_code == 401


def test_signup_duplicate_email_returns_409(client):
    client.post("/auth/signup", json={"email": "dup@example.com", "password": "password123"})
    duplicate = client.post("/auth/signup", json={"email": "dup@example.com", "password": "password456"})
    assert duplicate.status_code == 409


def test_login_wrong_password_returns_401(client):
    client.post("/auth/signup", json={"email": "user@example.com", "password": "password123"})
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_protected_route_rejects_missing_token(client):
    assert client.get("/jobs").status_code == 401


def test_protected_route_rejects_invalid_token(client):
    response = client.get("/jobs", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_create_and_list_jobs(client, auth_headers):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "link": "https://example.com/1"}

    created = client.post("/jobs", json=payload, headers=auth_headers)
    assert created.status_code == 200
    assert created.json()["id"] is not None

    listed = client.get("/jobs", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_jobs_are_isolated_per_user(client, auth_headers):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "link": "https://example.com/1"}
    client.post("/jobs", json=payload, headers=auth_headers)

    other_signup = client.post("/auth/signup", json={"email": "other@example.com", "password": "password123"})
    other_headers = {"Authorization": f"Bearer {other_signup.json()['token']}"}

    assert client.get("/jobs", headers=other_headers).json() == []


def test_create_job_duplicate_link_returns_409(client, auth_headers):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "link": "https://example.com/1"}
    client.post("/jobs", json=payload, headers=auth_headers)

    duplicate = client.post("/jobs", json=payload, headers=auth_headers)
    assert duplicate.status_code == 409


def test_create_list_and_delete_preference(client, auth_headers):
    created = client.post("/preferences", json={"keyword": "python", "kind": "include"}, headers=auth_headers)
    assert created.status_code == 200
    preference_id = created.json()["id"]

    listed = client.get("/preferences", headers=auth_headers)
    assert len(listed.json()) == 1

    deleted = client.delete(f"/preferences/{preference_id}", headers=auth_headers)
    assert deleted.status_code == 200
    assert client.get("/preferences", headers=auth_headers).json() == []


def test_create_preference_duplicate_returns_409(client, auth_headers):
    client.post("/preferences", json={"keyword": "python", "kind": "include"}, headers=auth_headers)
    duplicate = client.post("/preferences", json={"keyword": "python", "kind": "include"}, headers=auth_headers)
    assert duplicate.status_code == 409


def test_get_and_update_ingestion_settings(client, auth_headers):
    current = client.get("/ingestion/settings", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["poll_interval_hours"] == 4

    updated = client.put(
        "/ingestion/settings",
        json={
            "enable_rss_sources": True,
            "enable_linkedin_alerts": False,
            "enable_naukri_alerts": False,
            "enable_indeed_alerts": False,
            "allow_direct_scraping": False,
            "poll_interval_hours": 2,
        },
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["poll_interval_hours"] == 2
    assert client.get("/ingestion/settings", headers=auth_headers).json()["enable_rss_sources"] is True


def test_get_and_update_notification_settings(client, auth_headers):
    current = client.get("/notification-settings", headers=auth_headers)
    assert current.status_code == 200
    assert current.json()["telegram_bot_token"] is None

    updated = client.put(
        "/notification-settings",
        json={"telegram_bot_token": "token", "telegram_chat_id": "chat"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["telegram_bot_token"] == "token"
    assert client.get("/notification-settings", headers=auth_headers).json()["telegram_chat_id"] == "chat"


def test_ingest_runs_the_pipeline_and_records_history(client, auth_headers):
    result = client.post("/ingest", headers=auth_headers)
    assert result.status_code == 200
    body = result.json()
    assert body["fetched"] == 0  # every source disabled by default
    assert body["delivered"] == 0

    runs = client.get("/ingestion/runs", headers=auth_headers)
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert runs.json()[0]["status"] == "success"


def test_update_keywords_returns_flat_string_lists(client, auth_headers):
    response = client.post(
        "/ingest/keywords",
        json={"include_keywords": ["backend", "python"], "exclude_keywords": ["senior"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == {
        "include_keywords": ["backend", "python"],
        "exclude_keywords": ["senior"],
    }
