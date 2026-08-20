import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.ingestion.adapters.safe_registry import SafeAdapterRegistry
from app.ingestion.services.dedup_service import DedupService
from app.ingestion.services.embedding_service import EmbeddingService
from app.ingestion.services.matcher_service import MatcherService
from app.ingestion.services.notification_service import NotificationService
from app.models.ingestion_run import IngestionRun
from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository
from app.services.ingestion_settings_service import IngestionSettingsService
from app.services.notification_settings_service import NotificationSettingsService
from app.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.settings_service = IngestionSettingsService()
        self.preference_service = PreferenceService()
        self.notification_settings_service = NotificationSettingsService()
        self.dedup = DedupService()
        self.repository = JobRepository()
        self.run_repository = IngestionRunRepository()
        self.user_repository = UserRepository()
        self.embedding_service = embedding_service or EmbeddingService()

    def run_for_user(self, user_id: int) -> dict:
        """Runs one ingestion pass for a single user: fetch that user's enabled
        sources, match against their keywords, dedupe, persist, and notify via
        their own notification channels. This is what a manual `POST /ingest`
        triggers immediately, regardless of that user's poll_interval_hours --
        the due-check in run_all_users() is only for the scheduler/cron path."""
        started_at = datetime.now(timezone.utc).isoformat()

        try:
            ingestion_settings = self.settings_service.get_settings(user_id)
            registry = SafeAdapterRegistry.build_from_settings(user_id, ingestion_settings)
            matcher = MatcherService(self.preference_service.get_keyword_config(user_id))
            notifier = NotificationService(self.notification_settings_service.get_settings(user_id))

            candidates = registry.fetch_all()
            fetched_by_source = dict(registry.last_fetch_counts)
            matched = [candidate for candidate in candidates if matcher.match(candidate)]
            matched_by_source = dict(Counter(candidate.source for candidate in matched))
            deduped = self.dedup.filter_new(matched)

            new_jobs = []
            for candidate in deduped:
                job = self.repository.create_job_if_new(user_id, candidate)
                if job is not None:
                    new_jobs.append(job)
            new_candidates = new_jobs
            # Embeds each genuinely-new job once, right here at ingestion time --
            # see EmbeddingService for why (never re-embedded per match query).
            # A per-job failure is caught inside embed_jobs() and never aborts
            # the run; the job still gets notified/etc below regardless.
            self.embedding_service.embed_jobs(new_jobs)
            # Includes this run's new matches plus anything left over from a run
            # whose delivery failed partway through -- see JobRepository.list_unnotified.
            pending_notifications = self.repository.list_unnotified(user_id)
            delivered_ids = notifier.send(pending_notifications)
            self.repository.mark_notified(delivered_ids)
            delivered = len(delivered_ids)
        except Exception as exc:
            logger.exception("Ingestion run failed for user_id=%s", user_id)
            self._record_run(user_id, started_at, status="failed", error_message=str(exc))
            raise

        logger.info(
            "Ingestion run complete for user_id=%s: fetched=%d matched=%d new=%d delivered=%d | "
            "fetched by source: %s | matched by source: %s",
            user_id, len(candidates), len(matched), len(new_candidates), delivered,
            fetched_by_source, matched_by_source,
        )
        self._record_run(
            user_id,
            started_at,
            status="success",
            fetched_count=len(candidates),
            matched_count=len(matched),
            new_count=len(new_candidates),
            delivered_count=delivered,
        )
        return {
            "user_id": user_id,
            "fetched": len(candidates),
            "matched": len(matched),
            "new": len(new_candidates),
            "delivered": delivered,
            "fetched_by_source": fetched_by_source,
            "matched_by_source": matched_by_source,
        }

    def run_all_users(self) -> dict:
        """Runs one ingestion pass per user, skipping anyone not yet due per
        their own poll_interval_hours. Used by the scheduler tick and by
        scripts/run_ingestion_once.py (the GitHub Actions entrypoint) -- both
        callers get the same per-user cadence honored uniformly. One user's
        failure doesn't stop the rest from running (already logged/recorded by
        run_for_user's own error handling)."""
        results = []
        for user_id in self.user_repository.list_all_ids():
            poll_interval_hours = self.settings_service.get_settings(user_id).poll_interval_hours
            if not self._is_due(user_id, poll_interval_hours):
                continue
            try:
                results.append(self.run_for_user(user_id))
            except Exception:
                continue

        summary = {
            "users_run": len(results),
            "total_fetched": sum(r["fetched"] for r in results),
            "total_matched": sum(r["matched"] for r in results),
            "total_new": sum(r["new"] for r in results),
            "total_delivered": sum(r["delivered"] for r in results),
            "per_user": results,
        }
        logger.info(
            "Multi-user ingestion pass complete: %d user(s) ran, %d new job(s), %d delivered",
            summary["users_run"], summary["total_new"], summary["total_delivered"],
        )
        return summary

    def _is_due(self, user_id: int, poll_interval_hours: int) -> bool:
        last_finished_at = self.run_repository.most_recent_finished_at(user_id)
        if last_finished_at is None:
            return True
        last_finished = datetime.fromisoformat(last_finished_at)
        if last_finished.tzinfo is None:
            last_finished = last_finished.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - last_finished >= timedelta(hours=poll_interval_hours)

    def _record_run(
        self,
        user_id: int,
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
            user_id,
            IngestionRun(
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                status=status,
                fetched_count=fetched_count,
                matched_count=matched_count,
                new_count=new_count,
                delivered_count=delivered_count,
                error_message=error_message,
            ),
        )
