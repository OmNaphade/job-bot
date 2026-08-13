from app.models.notification_settings import NotificationSettings
from app.repositories.notification_settings_repository import NotificationSettingsRepository


class NotificationSettingsService:
    def __init__(self, repository: NotificationSettingsRepository | None = None) -> None:
        self.repository = repository or NotificationSettingsRepository()

    def get_settings(self, user_id: int) -> NotificationSettings:
        return self.repository.get(user_id)

    def update_settings(self, user_id: int, settings: NotificationSettings) -> NotificationSettings:
        return self.repository.update(user_id, settings)
