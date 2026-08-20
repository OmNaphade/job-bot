from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ResumeProfile(BaseModel):
    skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    years_experience: Optional[float] = None
    seniority: Optional[str] = None
    locations: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    source_filename: Optional[str] = None
    uploaded_at: datetime
    updated_at: datetime
