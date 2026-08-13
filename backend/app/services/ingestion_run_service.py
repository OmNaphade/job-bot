from typing import List

from app.models.ingestion_run import IngestionRun
from app.repositories.ingestion_run_repository import IngestionRunRepository


class IngestionRunService:
    def __init__(self, repository: IngestionRunRepository | None = None) -> None:
        self.repository = repository or IngestionRunRepository()

    def get_recent_runs(self, user_id: int, limit: int = 20) -> List[IngestionRun]:
        return self.repository.list_recent(user_id, limit)
