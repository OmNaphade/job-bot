from app.models.ingestion_settings import IngestionSettings
from app.repositories.ingestion_settings_repository import IngestionSettingsRepository


class IngestionSettingsService:
    def __init__(self, repository: IngestionSettingsRepository | None = None) -> None:
        self.repository = repository or IngestionSettingsRepository()

    def get_settings(self) -> IngestionSettings:
        return self.repository.get()

    def update_settings(self, settings: IngestionSettings) -> IngestionSettings:
        return self.repository.update(settings)
