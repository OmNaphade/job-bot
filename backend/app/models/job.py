from typing import Optional

from pydantic import BaseModel, Field


class JobBase(BaseModel):
    title: str = Field(..., min_length=1)
    company: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    link: str = Field(..., min_length=1)
    source: str = "manual"
    posted_at: Optional[str] = None


class JobCreate(JobBase):
    pass


class Job(JobBase):
    id: Optional[int] = None
