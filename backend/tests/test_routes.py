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


def test_create_and_list_jobs(client):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "link": "https://example.com/1"}

    created = client.post("/jobs", json=payload)
    assert created.status_code == 200
    assert created.json()["id"] is not None

    listed = client.get("/jobs")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_create_job_duplicate_link_returns_409(client):
    payload = {"title": "Backend Engineer", "company": "Acme", "location": "Remote", "link": "https://example.com/1"}
    client.post("/jobs", json=payload)

    duplicate = client.post("/jobs", json=payload)
    assert duplicate.status_code == 409


def test_create_list_and_delete_preference(client):
    created = client.post("/preferences", json={"keyword": "python", "kind": "include"})
    assert created.status_code == 200
    preference_id = created.json()["id"]

    listed = client.get("/preferences")
    assert len(listed.json()) == 1

    deleted = client.delete(f"/preferences/{preference_id}")
    assert deleted.status_code == 200
    assert client.get("/preferences").json() == []


def test_create_preference_duplicate_returns_409(client):
    client.post("/preferences", json={"keyword": "python", "kind": "include"})
    duplicate = client.post("/preferences", json={"keyword": "python", "kind": "include"})
    assert duplicate.status_code == 409


def test_get_and_update_ingestion_settings(client):
    current = client.get("/ingestion/settings")
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
    )
    assert updated.status_code == 200
    assert updated.json()["poll_interval_hours"] == 2
    assert client.get("/ingestion/settings").json()["enable_rss_sources"] is True


def test_ingest_runs_the_pipeline_and_records_history(client):
    result = client.post("/ingest")
    assert result.status_code == 200
    body = result.json()
    assert body["fetched"] == 0  # every source disabled by default
    assert body["delivered"] == 0

    runs = client.get("/ingestion/runs")
    assert runs.status_code == 200
    assert len(runs.json()) == 1
    assert runs.json()[0]["status"] == "success"


def test_update_keywords_returns_flat_string_lists(client):
    response = client.post(
        "/ingest/keywords",
        json={"include_keywords": ["backend", "python"], "exclude_keywords": ["senior"]},
    )
    assert response.status_code == 200
    assert response.json() == {
        "include_keywords": ["backend", "python"],
        "exclude_keywords": ["senior"],
    }
