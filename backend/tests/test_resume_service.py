import pytest

from app.repositories.resume_repository import ResumeRepository
from app.services.errors import AIExtractionError, ResumeUploadLimitExceeded
from app.services.resume_service import ResumeService


class _FakeGeminiClient:
    def __init__(self, profile: dict | None = None, embedding: list[float] | None = None, fail: bool = False):
        self.profile = profile or {
            "skills": ["Python"],
            "titles": ["Backend Engineer"],
            "years_experience": 5.0,
            "seniority": "senior",
            "locations": ["Remote"],
            "education": ["B.Sc. Computer Science"],
        }
        self.embedding = embedding or [0.1] * 768
        self.fail = fail
        self.extract_calls: list[str] = []
        self.embed_calls: list[str] = []

    def extract_resume_profile(self, resume_text: str) -> dict:
        if self.fail:
            raise RuntimeError("Gemini is down")
        self.extract_calls.append(resume_text)
        return self.profile

    def embed_text(self, text: str) -> list[float]:
        if self.fail:
            raise RuntimeError("Gemini is down")
        self.embed_calls.append(text)
        return self.embedding


def _pdf_bytes_with_text() -> bytes:
    import io

    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    pdf.drawString(72, 800, "Jane Doe, Backend Engineer")
    pdf.save()
    return buffer.getvalue()


def _blank_pdf_bytes() -> bytes:
    import io

    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    canvas.Canvas(buffer).save()
    return buffer.getvalue()


def test_upload_extracts_embeds_and_persists(test_user):
    fake_client = _FakeGeminiClient()
    service = ResumeService(ai_client=fake_client)

    profile = service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")

    assert profile.skills == ["Python"]
    assert profile.source_filename == "resume.pdf"
    assert len(fake_client.extract_calls) == 1
    assert "Jane Doe" in fake_client.extract_calls[0]
    assert len(fake_client.embed_calls) == 1
    assert ResumeRepository().get(test_user.id).skills == ["Python"]


def test_upload_records_an_upload_event(test_user):
    service = ResumeService(ai_client=_FakeGeminiClient())

    service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")

    from datetime import datetime, timedelta, timezone

    since = datetime.now(timezone.utc) - timedelta(days=1)
    assert ResumeRepository().count_uploads_since(test_user.id, since) == 1


def test_upload_raises_when_pdf_has_no_extractable_text(test_user):
    service = ResumeService(ai_client=_FakeGeminiClient())

    with pytest.raises(AIExtractionError):
        service.upload(test_user.id, _blank_pdf_bytes(), "blank.pdf")


def test_upload_raises_ai_extraction_error_when_no_ai_client_is_configured(test_user, monkeypatch):
    # Regression test: constructing GeminiClient() lazily inside upload() (no
    # ai_client override, no GOOGLE_API_KEY) used to raise a raw RuntimeError
    # that escaped the try/except and surfaced as an unhandled 500 -- caught
    # by a live smoke test, not by the other tests here, since they all
    # inject a fake client directly and never exercise this lazy-construction
    # path at all.
    import dataclasses

    from app.ai import gemini_client as gemini_client_module

    monkeypatch.setattr(
        gemini_client_module, "settings", dataclasses.replace(gemini_client_module.settings, google_api_key=None)
    )
    service = ResumeService()

    with pytest.raises(AIExtractionError):
        service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")


def test_upload_raises_ai_extraction_error_when_gemini_fails(test_user):
    service = ResumeService(ai_client=_FakeGeminiClient(fail=True))

    with pytest.raises(AIExtractionError):
        service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")


def _with_daily_cap(monkeypatch, cap: int) -> None:
    # `settings` is a frozen dataclass singleton -- can't setattr a field on
    # it directly, so rebind the module's `settings` name to a copy with the
    # one field changed (same pattern as tests/test_auth_service.py).
    import dataclasses

    from app.services import resume_service as resume_service_module

    monkeypatch.setattr(resume_service_module, "settings", dataclasses.replace(resume_service_module.settings, resume_upload_daily_cap=cap))


def test_upload_enforces_the_daily_cap(test_user, monkeypatch):
    _with_daily_cap(monkeypatch, 2)
    service = ResumeService(ai_client=_FakeGeminiClient())

    service.upload(test_user.id, _pdf_bytes_with_text(), "resume1.pdf")
    service.upload(test_user.id, _pdf_bytes_with_text(), "resume2.pdf")

    with pytest.raises(ResumeUploadLimitExceeded):
        service.upload(test_user.id, _pdf_bytes_with_text(), "resume3.pdf")


def test_upload_does_not_call_gemini_when_the_cap_is_already_reached(test_user, monkeypatch):
    _with_daily_cap(monkeypatch, 0)
    fake_client = _FakeGeminiClient()
    service = ResumeService(ai_client=fake_client)

    with pytest.raises(ResumeUploadLimitExceeded):
        service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")

    assert fake_client.extract_calls == []
    assert fake_client.embed_calls == []


def test_get_profile_returns_none_when_unset(test_user):
    assert ResumeService().get_profile(test_user.id) is None


def test_get_profile_returns_the_persisted_profile(test_user):
    service = ResumeService(ai_client=_FakeGeminiClient())
    service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")

    assert ResumeService().get_profile(test_user.id).skills == ["Python"]


def test_delete_removes_the_profile(test_user):
    service = ResumeService(ai_client=_FakeGeminiClient())
    service.upload(test_user.id, _pdf_bytes_with_text(), "resume.pdf")

    service.delete(test_user.id)

    assert ResumeService().get_profile(test_user.id) is None
