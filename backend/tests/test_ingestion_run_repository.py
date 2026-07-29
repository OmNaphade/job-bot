from app.models.ingestion_run import IngestionRun
from app.repositories.ingestion_run_repository import IngestionRunRepository


def _run(status: str = "success", error_message: str | None = None) -> IngestionRun:
    return IngestionRun(
        started_at="2026-07-30T09:00:00+00:00",
        finished_at="2026-07-30T09:00:05+00:00",
        status=status,
        fetched_count=10,
        matched_count=3,
        new_count=2,
        delivered_count=2,
        error_message=error_message,
    )


def test_record_assigns_an_id(tmp_db):
    recorded = IngestionRunRepository().record(_run())
    assert recorded.id is not None


def test_list_recent_returns_newest_first(tmp_db):
    repo = IngestionRunRepository()
    repo.record(_run(status="success"))
    repo.record(_run(status="failed", error_message="boom"))

    runs = repo.list_recent(limit=10)

    assert [run.status for run in runs] == ["failed", "success"]
    assert runs[0].error_message == "boom"


def test_list_recent_respects_limit(tmp_db):
    repo = IngestionRunRepository()
    for _ in range(5):
        repo.record(_run())

    assert len(repo.list_recent(limit=2)) == 2
