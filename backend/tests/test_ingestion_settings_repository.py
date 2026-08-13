from app.core.security import hash_password
from app.models.ingestion_settings import IngestionSettings
from app.repositories.ingestion_settings_repository import IngestionSettingsRepository
from app.repositories.user_repository import UserRepository


def test_get_lazily_creates_and_returns_seeded_defaults(test_user):
    settings = IngestionSettingsRepository().get(test_user.id)

    assert settings == IngestionSettings()


def test_update_persists_and_round_trips(test_user):
    repo = IngestionSettingsRepository()
    updated = IngestionSettings(
        enable_rss_sources=True,
        enable_linkedin_alerts=True,
        enable_naukri_alerts=False,
        enable_indeed_alerts=True,
        allow_direct_scraping=False,
        poll_interval_hours=6,
    )

    repo.update(test_user.id, updated)

    assert repo.get(test_user.id) == updated


def test_settings_are_isolated_per_user(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = IngestionSettingsRepository()
    repo.update(test_user.id, IngestionSettings(enable_rss_sources=True))

    assert repo.get(other_user.id) == IngestionSettings()


def test_update_before_any_get_still_persists(test_user):
    """update() must not depend on get() having already lazily created a row."""
    repo = IngestionSettingsRepository()
    updated = IngestionSettings(enable_rss_sources=True, poll_interval_hours=2)

    repo.update(test_user.id, updated)

    assert repo.get(test_user.id) == updated
