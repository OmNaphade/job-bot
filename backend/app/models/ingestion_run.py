from typing import Literal, Optional

from pydantic import BaseModel


class IngestionRun(BaseModel):
    id: Optional[int] = None
    started_at: str
    finished_at: str
    status: Literal["success", "failed"]
    fetched_count: int
    matched_count: int
    new_count: int
    delivered_count: int
    error_message: Optional[str] = None
