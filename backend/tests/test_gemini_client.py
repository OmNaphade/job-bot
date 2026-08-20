from types import SimpleNamespace

import pytest

from app.ai import gemini_client as gemini_client_module
from app.ai.gemini_client import EMBEDDING_DIMENSIONS, GeminiClient, ResumeExtraction


@pytest.fixture
def fake_settings(monkeypatch):
    settings = SimpleNamespace(
        google_api_key="fake-key-for-tests",
        gemini_extraction_model="gemini-2.5-flash",
        gemini_embedding_model="text-embedding-004",
    )
    monkeypatch.setattr(gemini_client_module, "settings", settings)
    return settings


def test_constructor_raises_without_an_api_key(monkeypatch):
    monkeypatch.setattr(
        gemini_client_module,
        "settings",
        SimpleNamespace(google_api_key=None, gemini_extraction_model="x", gemini_embedding_model="y"),
    )

    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GeminiClient()


def test_extract_resume_profile_returns_the_parsed_dict(fake_settings, monkeypatch):
    client = GeminiClient()
    parsed = ResumeExtraction(
        skills=["Python", "Postgres"],
        titles=["Backend Engineer"],
        years_experience=5.0,
        seniority="senior",
        locations=["Remote"],
        education=["B.Sc. Computer Science"],
    )

    captured = {}

    def _fake_generate_content(*, model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["response_schema"] = config.response_schema
        return SimpleNamespace(parsed=parsed, text=parsed.model_dump_json())

    monkeypatch.setattr(client._client.models, "generate_content", _fake_generate_content)

    result = client.extract_resume_profile("Jane Doe, Backend Engineer, 5 years Python/Postgres experience.")

    assert result == parsed.model_dump()
    assert captured["model"] == "gemini-2.5-flash"
    assert "Jane Doe" in captured["contents"]
    assert captured["response_schema"] is ResumeExtraction


def test_extract_resume_profile_raises_when_gemini_returns_unparseable_output(fake_settings, monkeypatch):
    client = GeminiClient()
    monkeypatch.setattr(
        client._client.models,
        "generate_content",
        lambda **kwargs: SimpleNamespace(parsed=None, text="not json"),
    )

    with pytest.raises(RuntimeError, match="did not return a schema-conforming response"):
        client.extract_resume_profile("some resume text")


def test_embed_text_returns_the_embedding_vector(fake_settings, monkeypatch):
    client = GeminiClient()
    vector = [0.1] * EMBEDDING_DIMENSIONS
    captured = {}

    def _fake_embed_content(*, model, contents, config):
        captured["model"] = model
        captured["contents"] = contents
        captured["output_dimensionality"] = config.output_dimensionality
        return SimpleNamespace(embeddings=[SimpleNamespace(values=vector)])

    monkeypatch.setattr(client._client.models, "embed_content", _fake_embed_content)

    result = client.embed_text("some resume text")

    assert result == vector
    assert captured["model"] == "text-embedding-004"
    assert captured["output_dimensionality"] == EMBEDDING_DIMENSIONS


def test_embed_text_raises_when_gemini_returns_no_embeddings(fake_settings, monkeypatch):
    client = GeminiClient()
    monkeypatch.setattr(
        client._client.models,
        "embed_content",
        lambda **kwargs: SimpleNamespace(embeddings=[]),
    )

    with pytest.raises(RuntimeError, match="no embeddings"):
        client.embed_text("some resume text")
