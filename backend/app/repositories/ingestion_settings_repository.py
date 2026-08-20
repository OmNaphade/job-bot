from app.db import database
from app.models.ingestion_settings import IngestionSettings

_DEFAULT_COLUMNS = (
    "enable_rss_sources, enable_linkedin_alerts, enable_naukri_alerts, "
    "enable_indeed_alerts, allow_direct_scraping, poll_interval_hours"
)


class IngestionSettingsRepository:
    def get(self, user_id: int) -> IngestionSettings:
        # There's no longer a single pre-seeded singleton row (see
        # 0001_initial_schema.py, which replaced the old singleton design
        # outright rather than porting it) -- a fresh default row is created
        # lazily on first access for a user who hasn't configured anything
        # yet, same "everything off by default" defaults the old singleton
        # shipped with.
        with database.db_session() as connection:
            connection.execute(
                f"""
                INSERT INTO ingestion_settings (user_id, {_DEFAULT_COLUMNS})
                VALUES (%s, false, false, false, false, false, 4)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )
            row = connection.execute(
                f"SELECT {_DEFAULT_COLUMNS} FROM ingestion_settings WHERE user_id = %s",
                (user_id,),
            ).fetchone()
        return IngestionSettings(**dict(row))

    def update(self, user_id: int, settings: IngestionSettings) -> IngestionSettings:
        with database.db_session() as connection:
            connection.execute(
                f"""
                INSERT INTO ingestion_settings (user_id, {_DEFAULT_COLUMNS})
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    enable_rss_sources = excluded.enable_rss_sources,
                    enable_linkedin_alerts = excluded.enable_linkedin_alerts,
                    enable_naukri_alerts = excluded.enable_naukri_alerts,
                    enable_indeed_alerts = excluded.enable_indeed_alerts,
                    allow_direct_scraping = excluded.allow_direct_scraping,
                    poll_interval_hours = excluded.poll_interval_hours
                """,
                (
                    user_id,
                    settings.enable_rss_sources,
                    settings.enable_linkedin_alerts,
                    settings.enable_naukri_alerts,
                    settings.enable_indeed_alerts,
                    settings.allow_direct_scraping,
                    settings.poll_interval_hours,
                ),
            )
        return settings
