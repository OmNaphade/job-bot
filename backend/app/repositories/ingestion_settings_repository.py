from app.db.database import db_session
from app.models.ingestion_settings import IngestionSettings

_DEFAULT_COLUMNS = (
    "enable_rss_sources, enable_linkedin_alerts, enable_naukri_alerts, "
    "enable_indeed_alerts, allow_direct_scraping, poll_interval_hours"
)


class IngestionSettingsRepository:
    def get(self, user_id: int) -> IngestionSettings:
        # There's no longer a single pre-seeded singleton row (see
        # _migrate_ingestion_settings_to_per_user in database.py) -- a fresh
        # default row is created lazily on first access for a user who hasn't
        # configured anything yet, same "everything off by default" defaults
        # the old singleton shipped with.
        with db_session() as connection:
            connection.execute(
                f"""
                INSERT OR IGNORE INTO ingestion_settings (user_id, {_DEFAULT_COLUMNS})
                VALUES (?, 0, 0, 0, 0, 0, 4)
                """,
                (user_id,),
            )
            row = connection.execute(
                f"SELECT {_DEFAULT_COLUMNS} FROM ingestion_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return IngestionSettings(
            enable_rss_sources=bool(row["enable_rss_sources"]),
            enable_linkedin_alerts=bool(row["enable_linkedin_alerts"]),
            enable_naukri_alerts=bool(row["enable_naukri_alerts"]),
            enable_indeed_alerts=bool(row["enable_indeed_alerts"]),
            allow_direct_scraping=bool(row["allow_direct_scraping"]),
            poll_interval_hours=row["poll_interval_hours"],
        )

    def update(self, user_id: int, settings: IngestionSettings) -> IngestionSettings:
        with db_session() as connection:
            connection.execute(
                f"""
                INSERT INTO ingestion_settings (user_id, {_DEFAULT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    enable_rss_sources = excluded.enable_rss_sources,
                    enable_linkedin_alerts = excluded.enable_linkedin_alerts,
                    enable_naukri_alerts = excluded.enable_naukri_alerts,
                    enable_indeed_alerts = excluded.enable_indeed_alerts,
                    allow_direct_scraping = excluded.allow_direct_scraping,
                    poll_interval_hours = excluded.poll_interval_hours
                """,
                (
                    user_id,
                    int(settings.enable_rss_sources),
                    int(settings.enable_linkedin_alerts),
                    int(settings.enable_naukri_alerts),
                    int(settings.enable_indeed_alerts),
                    int(settings.allow_direct_scraping),
                    settings.poll_interval_hours,
                ),
            )
        return settings
