from typing import Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import settings

# Vector columns in the schema are `vector(768)` (0001_initial_schema.py) --
# requested explicitly on every embed call so this stays correct even if
# GEMINI_EMBEDDING_MODEL is later pointed at a model whose *default* output
# dimensionality differs (e.g. gemini-embedding-001 defaults to 3072).
EMBEDDING_DIMENSIONS = 768


class ResumeExtraction(BaseModel):
    """Gemini's structured-output contract for resume parsing -- deliberately
    separate from app.models.resume.ResumeProfile (the public API/DB shape),
    since this is specifically what we ask the model for, not what we persist
    or return (which also carries embedding/timestamps/filename)."""

    skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    years_experience: Optional[float] = None
    seniority: Optional[str] = None
    locations: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)


_EXTRACTION_PROMPT = """You are extracting structured information from a resume for a job-matching system.
Read the resume text below and extract:
- skills: a flat list of concrete technical/professional skills (e.g. "Python", "AWS", "project management")
- titles: job titles this person has held or is qualified for
- years_experience: total years of professional experience as a number, or null if it can't be determined
- seniority: one of "junior", "mid", "senior", "lead", "executive", or null if unclear
- locations: cities/regions/countries this person has worked in or wants to work in
- education: degrees/institutions, as short strings (e.g. "B.Sc. Computer Science, MIT")

Resume text:
---
{resume_text}
---
"""


class GeminiClient:
    def __init__(self) -> None:
        if not settings.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set -- required for resume parsing and job matching.")
        self._client = genai.Client(api_key=settings.google_api_key)

    def extract_resume_profile(self, resume_text: str) -> dict:
        response = self._client.models.generate_content(
            model=settings.gemini_extraction_model,
            contents=_EXTRACTION_PROMPT.format(resume_text=resume_text),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ResumeExtraction,
            ),
        )
        if response.parsed is None:
            raise RuntimeError(f"Gemini did not return a schema-conforming response: {response.text!r}")
        return response.parsed.model_dump()

    def embed_text(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIMENSIONS),
        )
        if not response.embeddings:
            raise RuntimeError("Gemini returned no embeddings for the given text.")
        return response.embeddings[0].values
