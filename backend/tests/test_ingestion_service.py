from app.ingestion.services.ingestion_service import IngestionService
from app.repositories.ingestion_run_repository import IngestionRunRepository


def test_run_with_all_sources_disabled_records_a_successful_run(tmp_db):
    result = IngestionService().run()

    assert result == {"fetched": 0, "matched": 0, "new": 0, "delivered": 0}

    runs = IngestionRunRepository().list_recent(limit=1)
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].error_message is None


def test_run_records_a_failed_run_and_reraises(tmp_db, monkeypatch):
    def _boom(self):
        raise RuntimeError("adapter exploded")

    monkeypatch.setattr(
        "app.ingestion.adapters.safe_registry.SafeAdapterRegistry.fetch_all", _boom
    )

    service = IngestionService()
    try:
        service.run()
        assert False, "expected RuntimeError to propagate"
    except RuntimeError:
        pass

    runs = IngestionRunRepository().list_recent(limit=1)
    assert len(runs) == 1
    assert runs[0].status == "failed"
    assert "adapter exploded" in runs[0].error_message
