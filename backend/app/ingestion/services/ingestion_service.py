import logging
from datetime import datetime, timezone

from app.ingestion.adapters.safe_registry import SafeAdapterRegistry
from app.ingestion.services.dedup_service import DedupService
from app.ingestion.services.matcher_service import MatcherService
from app.ingestion.services.notification_service import NotificationService
from app.models.ingestion_run import IngestionRun
from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.job_repository import JobRepository
from app.services.ingestion_settings_service import IngestionSettingsService
from app.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self) -> None:
        self.settings_service = IngestionSettingsService()
        self.preference_service = PreferenceService()
        self.dedup = DedupService()
        self.notifier = NotificationService()
        self.repository = JobRepository()
        self.run_repository = IngestionRunRepository()

    def run(self) -> dict[str, int]:
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            ingestion_settings = self.settings_service.get_settings()
            registry = SafeAdapterRegistry.build_from_settings(ingestion_settings)
            matcher = MatcherService(self.preference_service.get_keyword_config())

            candidates = registry.fetch_all()
            matched = [candidate for candidate in candidates if matcher.match(candidate)]
            deduped = self.dedup.filter_new(matched)

            new_candidates = [
                candidate for candidate in deduped if self.repository.create_job_if_new(candidate) is not None
            ]
            delivered = self.notifier.send(new_candidates)
        except Exception as exc:
            logger.exception("Ingestion run failed")
            self._record_run(started_at, status="failed", error_message=str(exc))
            raise

        logger.info(
            "Ingestion run complete: fetched=%d matched=%d new=%d delivered=%d",
            len(candidates), len(matched), len(new_candidates), delivered,
        )
        self._record_run(
            started_at,
            status="success",
            fetched_count=len(candidates),
            matched_count=len(matched),
            new_count=len(new_candidates),
            delivered_count=delivered,
        )
        return {"fetched": len(candidates), "matched": len(matched), "new": len(new_candidates), "delivered": delivered}

    def _record_run(
        self,
        started_at: str,
        *,
        status: str,
        fetched_count: int = 0,
        matched_count: int = 0,
        new_count: int = 0,
        delivered_count: int = 0,
        error_message: str | None = None,
    ) -> None:
        self.run_repository.record(
            IngestionRun(
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                status=status,
                fetched_count=fetched_count,
                matched_count=matched_count,
                new_count=new_count,
                delivered_count=delivered_count,
                error_message=error_message,
            )
        )
