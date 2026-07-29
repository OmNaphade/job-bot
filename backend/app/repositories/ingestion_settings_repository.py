from app.db.database import db_session
from app.models.ingestion_settings import IngestionSettings


class IngestionSettingsRepository:
    def get(self) -> IngestionSettings:
        with db_session() as connection:
            row = connection.execute(
                """
                SELECT enable_rss_sources, enable_linkedin_alerts, enable_naukri_alerts,
                       allow_direct_scraping, poll_interval_hours
                FROM ingestion_settings WHERE id = 1
                """
            ).fetchone()
        return IngestionSettings(
            enable_rss_sources=bool(row["enable_rss_sources"]),
            enable_linkedin_alerts=bool(row["enable_linkedin_alerts"]),
            enable_naukri_alerts=bool(row["enable_naukri_alerts"]),
            allow_direct_scraping=bool(row["allow_direct_scraping"]),
            poll_interval_hours=row["poll_interval_hours"],
        )

    def update(self, settings: IngestionSettings) -> IngestionSettings:
        with db_session() as connection:
            connection.execute(
                """
                UPDATE ingestion_settings
                SET enable_rss_sources = ?,
                    enable_linkedin_alerts = ?,
                    enable_naukri_alerts = ?,
                    allow_direct_scraping = ?,
                    poll_interval_hours = ?
                WHERE id = 1
                """,
                (
                    int(settings.enable_rss_sources),
                    int(settings.enable_linkedin_alerts),
                    int(settings.enable_naukri_alerts),
                    int(settings.allow_direct_scraping),
                    settings.poll_interval_hours,
                ),
            )
        return settings
