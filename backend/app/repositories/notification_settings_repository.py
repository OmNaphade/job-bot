from app.db import database
from app.models.notification_settings import NotificationSettings

_COLUMNS = "telegram_bot_token, telegram_chat_id, slack_webhook_url, discord_webhook_url"


class NotificationSettingsRepository:
    def get(self, user_id: int) -> NotificationSettings:
        with database.db_session() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM notification_settings WHERE user_id = %s",
                (user_id,),
            ).fetchone()
        if row is None:
            return NotificationSettings()
        return NotificationSettings(**dict(row))

    def update(self, user_id: int, settings: NotificationSettings) -> NotificationSettings:
        with database.db_session() as connection:
            connection.execute(
                f"""
                INSERT INTO notification_settings (user_id, {_COLUMNS})
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    telegram_bot_token = excluded.telegram_bot_token,
                    telegram_chat_id = excluded.telegram_chat_id,
                    slack_webhook_url = excluded.slack_webhook_url,
                    discord_webhook_url = excluded.discord_webhook_url
                """,
                (
                    user_id,
                    settings.telegram_bot_token,
                    settings.telegram_chat_id,
                    settings.slack_webhook_url,
                    settings.discord_webhook_url,
                ),
            )
        return settings
