import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from app.api import resume_routes
from app.api.routes import router
from app.models.resume import ResumeProfile
from app.services.errors import AIExtractionError, ResumeUploadLimitExceeded


def _pdf_bytes() -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 800, "Jane Doe, Backend Engineer")
    pdf.save()
    return buffer.getvalue()


class _FakeResumeService:
    def __init__(self, profile: ResumeProfile | None = None, upload_error: Exception | None = None):
        self.profile = profile
        self.upload_error = upload_error
        self.deleted_for: list[int] = []

    def upload(self, user_id, pdf_bytes, filename):
        if self.upload_error:
            raise self.upload_error
        self.profile = ResumeProfile(
            skills=["Python"],
            titles=["Backend Engineer"],
            years_experience=5.0,
            seniority="senior",
            locations=["Remote"],
            education=["B.Sc. Computer Science"],
            source_filename=filename,
            uploaded_at="2026-08-19T00:00:00+00:00",
            updated_at="2026-08-19T00:00:00+00:00",
        )
        return self.profile

    def get_profile(self, user_id):
        return self.profile

    def delete(self, user_id):
        self.deleted_for.append(user_id)
        self.profile = None


@pytest.fixture
def fake_resume_service():
    return _FakeResumeService()


@pytest.fixture
def client(tmp_db, fake_resume_service):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[resume_routes.get_resume_service] = lambda: fake_resume_service
    return TestClient(app)


def test_upload_resume_returns_the_parsed_profile(client, auth_headers):
    response = client.post(
        "/resume",
        headers=auth_headers,
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["skills"] == ["Python"]
    assert body["source_filename"] == "resume.pdf"


def test_upload_resume_rejects_non_pdf_content_type(client, auth_headers):
    response = client.post(
        "/resume",
        headers=auth_headers,
        files={"file": ("resume.txt", b"not a pdf", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_resume_returns_429_when_daily_cap_exceeded(client, auth_headers, fake_resume_service):
    fake_resume_service.upload_error = ResumeUploadLimitExceeded("Daily resume upload limit (5) reached")

    response = client.post(
        "/resume",
        headers=auth_headers,
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 429


def test_upload_resume_returns_502_when_ai_extraction_fails(client, auth_headers, fake_resume_service):
    fake_resume_service.upload_error = AIExtractionError("Couldn't process your resume right now")

    response = client.post(
        "/resume",
        headers=auth_headers,
        files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 502


def test_get_resume_returns_null_when_none_uploaded(client, auth_headers):
    response = client.get("/resume", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() is None


def test_get_resume_returns_the_current_profile(client, auth_headers, fake_resume_service):
    client.post("/resume", headers=auth_headers, files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")})

    response = client.get("/resume", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["skills"] == ["Python"]


def test_delete_resume_clears_the_profile(client, auth_headers, fake_resume_service):
    client.post("/resume", headers=auth_headers, files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")})

    response = client.delete("/resume", headers=auth_headers)

    assert response.status_code == 200
    assert client.get("/resume", headers=auth_headers).json() is None


def test_resume_endpoints_require_auth(client):
    assert client.get("/resume").status_code == 401
    assert client.delete("/resume").status_code == 401
    assert client.post("/resume", files={"file": ("resume.pdf", _pdf_bytes(), "application/pdf")}).status_code == 401
