from app.core.security import hash_password
from app.models.notification_settings import NotificationSettings
from app.repositories.notification_settings_repository import NotificationSettingsRepository
from app.repositories.user_repository import UserRepository


def test_get_returns_empty_defaults_when_unconfigured(test_user):
    settings = NotificationSettingsRepository().get(test_user.id)

    assert settings == NotificationSettings()


def test_update_persists_and_round_trips(test_user):
    repo = NotificationSettingsRepository()
    updated = NotificationSettings(
        telegram_bot_token="token",
        telegram_chat_id="chat",
        slack_webhook_url="https://hooks.slack.test/abc",
        discord_webhook_url="https://discord.test/webhooks/abc",
    )

    repo.update(test_user.id, updated)

    assert repo.get(test_user.id) == updated


def test_update_twice_overwrites_rather_than_duplicates(test_user):
    repo = NotificationSettingsRepository()
    repo.update(test_user.id, NotificationSettings(telegram_bot_token="first"))
    repo.update(test_user.id, NotificationSettings(telegram_bot_token="second"))

    assert repo.get(test_user.id).telegram_bot_token == "second"


def test_settings_are_isolated_per_user(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = NotificationSettingsRepository()
    repo.update(test_user.id, NotificationSettings(telegram_bot_token="mine"))

    assert repo.get(other_user.id) == NotificationSettings()
