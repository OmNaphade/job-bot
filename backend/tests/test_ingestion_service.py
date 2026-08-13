from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.ingestion.services.ingestion_service import IngestionService
from app.models.ingestion_run import IngestionRun
from app.models.ingestion_settings import IngestionSettings
from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.ingestion_settings_repository import IngestionSettingsRepository
from app.repositories.user_repository import UserRepository


def test_run_for_user_with_all_sources_disabled_records_a_successful_run(test_user):
    result = IngestionService().run_for_user(test_user.id)

    assert result["user_id"] == test_user.id
    assert result["fetched"] == 0
    assert result["matched"] == 0
    assert result["new"] == 0
    assert result["delivered"] == 0
    # Every registered source is reported, even disabled ones fetching nothing.
    assert result["fetched_by_source"]
    assert all(count == 0 for count in result["fetched_by_source"].values())
    assert result["matched_by_source"] == {}

    runs = IngestionRunRepository().list_recent(test_user.id, limit=1)
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].error_message is None


def test_run_for_user_records_a_failed_run_and_reraises(test_user, monkeypatch):
    def _boom(self):
        raise RuntimeError("adapter exploded")

    monkeypatch.setattr(
        "app.ingestion.adapters.safe_registry.SafeAdapterRegistry.fetch_all", _boom
    )

    service = IngestionService()
    try:
        service.run_for_user(test_user.id)
        assert False, "expected RuntimeError to propagate"
    except RuntimeError:
        pass

    runs = IngestionRunRepository().list_recent(test_user.id, limit=1)
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert "adapter exploded" in runs[0].error_message


def test_run_all_users_runs_every_user_once(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))

    summary = IngestionService().run_all_users()

    assert summary["users_run"] == 2
    assert {run["user_id"] for run in summary["per_user"]} == {test_user.id, other_user.id}


def test_run_all_users_skips_a_user_not_yet_due(test_user, tmp_db):
    IngestionSettingsRepository().update(test_user.id, IngestionSettings(poll_interval_hours=4))
    IngestionRunRepository().record(
        test_user.id,
        IngestionRun(
            started_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            finished_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            status="success",
            fetched_count=0,
            matched_count=0,
            new_count=0,
            delivered_count=0,
        ),
    )

    summary = IngestionService().run_all_users()

    assert summary["users_run"] == 0


def test_run_all_users_runs_a_user_who_is_overdue(test_user, tmp_db):
    IngestionSettingsRepository().update(test_user.id, IngestionSettings(poll_interval_hours=1))
    IngestionRunRepository().record(
        test_user.id,
        IngestionRun(
            started_at=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
            finished_at=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
            status="success",
            fetched_count=0,
            matched_count=0,
            new_count=0,
            delivered_count=0,
        ),
    )

    summary = IngestionService().run_all_users()

    assert summary["users_run"] == 1


def test_run_all_users_continues_after_one_users_run_fails(test_user, tmp_db, monkeypatch):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    original_run_for_user = IngestionService.run_for_user

    def _run_for_user(self, user_id):
        if user_id == test_user.id:
            raise RuntimeError("boom")
        return original_run_for_user(self, user_id)

    monkeypatch.setattr(IngestionService, "run_for_user", _run_for_user)

    summary = IngestionService().run_all_users()

    assert summary["users_run"] == 1
    assert summary["per_user"][0]["user_id"] == other_user.id
