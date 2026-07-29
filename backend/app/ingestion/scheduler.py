import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.ingestion.services.ingestion_service import IngestionService
from app.services.ingestion_settings_service import IngestionSettingsService

logger = logging.getLogger(__name__)

JOB_ID = "ingestion_poll"

_scheduler = BackgroundScheduler()


def _run_ingestion_job() -> None:
    try:
        result = IngestionService().run()
        logger.info("Scheduled ingestion run finished: %s", result)
    except Exception:
        logger.exception("Scheduled ingestion run failed; will retry on the next interval")


def start() -> None:
    interval_hours = IngestionSettingsService().get_settings().poll_interval_hours
    _scheduler.add_job(
        _run_ingestion_job,
        trigger=IntervalTrigger(hours=interval_hours),
        id=JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Ingestion scheduler started: polling every %d hour(s)", interval_hours)


def reschedule(interval_hours: int) -> None:
    if not _scheduler.running:
        return
    _scheduler.reschedule_job(JOB_ID, trigger=IntervalTrigger(hours=interval_hours))
    logger.info("Ingestion scheduler rescheduled: polling every %d hour(s)", interval_hours)


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
