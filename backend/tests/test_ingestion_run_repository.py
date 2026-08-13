from app.core.security import hash_password
from app.models.ingestion_run import IngestionRun
from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.user_repository import UserRepository


def _run(status: str = "success", error_message: str | None = None, finished_at: str = "2026-07-30T09:00:05+00:00") -> IngestionRun:
    return IngestionRun(
        started_at="2026-07-30T09:00:00+00:00",
        finished_at=finished_at,
        status=status,
        fetched_count=10,
        matched_count=3,
        new_count=2,
        delivered_count=2,
        error_message=error_message,
    )


def test_record_assigns_an_id(test_user):
    recorded = IngestionRunRepository().record(test_user.id, _run())
    assert recorded.id is not None


def test_list_recent_returns_newest_first(test_user):
    repo = IngestionRunRepository()
    repo.record(test_user.id, _run(status="success"))
    repo.record(test_user.id, _run(status="failed", error_message="boom"))

    runs = repo.list_recent(test_user.id, limit=10)

    assert [run.status for run in runs] == ["failed", "success"]
    assert runs[0].error_message == "boom"


def test_list_recent_respects_limit(test_user):
    repo = IngestionRunRepository()
    for _ in range(5):
        repo.record(test_user.id, _run())

    assert len(repo.list_recent(test_user.id, limit=2)) == 2


def test_list_recent_only_returns_the_calling_users_runs(test_user, tmp_db):
    other_user = UserRepository().create("other@example.com", hash_password("password123"))
    repo = IngestionRunRepository()
    repo.record(other_user.id, _run())

    assert repo.list_recent(test_user.id, limit=10) == []


def test_most_recent_finished_at_returns_none_when_no_runs(test_user):
    assert IngestionRunRepository().most_recent_finished_at(test_user.id) is None


def test_most_recent_finished_at_returns_latest_runs_timestamp(test_user):
    repo = IngestionRunRepository()
    repo.record(test_user.id, _run(finished_at="2026-07-30T09:00:05+00:00"))
    repo.record(test_user.id, _run(finished_at="2026-07-30T10:00:05+00:00"))

    assert repo.most_recent_finished_at(test_user.id) == "2026-07-30T10:00:05+00:00"
