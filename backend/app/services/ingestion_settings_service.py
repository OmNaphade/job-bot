from app.models.ingestion_settings import IngestionSettings
from app.repositories.ingestion_settings_repository import IngestionSettingsRepository


class IngestionSettingsService:
    def __init__(self, repository: IngestionSettingsRepository | None = None) -> None:
        self.repository = repository or IngestionSettingsRepository()

    def get_settings(self, user_id: int) -> IngestionSettings:
        return self.repository.get(user_id)

    def update_settings(self, user_id: int, settings: IngestionSettings) -> IngestionSettings:
        return self.repository.update(user_id, settings)
