from app.models.ingestion_settings import IngestionSettings
from app.repositories.ingestion_settings_repository import IngestionSettingsRepository


def test_get_returns_seeded_defaults(tmp_db):
    settings = IngestionSettingsRepository().get()

    assert settings == IngestionSettings()


def test_update_persists_and_round_trips(tmp_db):
    repo = IngestionSettingsRepository()
    updated = IngestionSettings(
        enable_rss_sources=True,
        enable_linkedin_alerts=True,
        enable_naukri_alerts=False,
        enable_indeed_alerts=True,
        allow_direct_scraping=False,
        poll_interval_hours=6,
    )

    repo.update(updated)

    assert repo.get() == updated
