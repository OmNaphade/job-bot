import logging

from app.ingestion.adapters.safe_registry import SafeAdapterRegistry
from app.ingestion.services.dedup_service import DedupService
from app.ingestion.services.matcher_service import MatcherService
from app.ingestion.services.notification_service import NotificationService
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

    def run(self) -> dict[str, int]:
        ingestion_settings = self.settings_service.get_settings()
        registry = SafeAdapterRegistry.build_from_settings(ingestion_settings)
        matcher = MatcherService(self.preference_service.get_keyword_config())

        candidates = registry.fetch_all()
        matched = [candidate for candidate in candidates if matcher.match(candidate)]
        deduped = self.dedup.filter_new(matched)

        new_candidates = [candidate for candidate in deduped if self.repository.create_job_if_new(candidate) is not None]
        delivered = self.notifier.send(new_candidates)

        logger.info(
            "Ingestion run complete: fetched=%d matched=%d new=%d delivered=%d",
            len(candidates), len(matched), len(new_candidates), delivered,
        )
        return {"matched": len(matched), "new": len(new_candidates), "delivered": delivered}
