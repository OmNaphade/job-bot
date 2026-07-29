from typing import Literal, Optional

from pydantic import BaseModel, Field

PreferenceKind = Literal["include", "exclude"]


class PreferenceBase(BaseModel):
    keyword: str = Field(..., min_length=1)
    kind: PreferenceKind = "include"
    location: Optional[str] = None


class PreferenceCreate(PreferenceBase):
    pass


class Preference(PreferenceBase):
    id: Optional[int] = None


class KeywordUpdate(BaseModel):
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
