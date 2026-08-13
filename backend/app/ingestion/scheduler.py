import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.ingestion.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

JOB_ID = "ingestion_poll"
# Fixed short tick -- individual users can each set their own poll_interval_hours
# (1-24h), so one global interval can't honor everyone's setting. Instead this
# ticks frequently and IngestionService.run_all_users() decides per-user
# whether they're actually due yet, based on their own last run. 15 minutes is
# finer than the shortest allowed poll_interval_hours (1h) without polling so
# often it's wasteful.
TICK_MINUTES = 15

_scheduler = BackgroundScheduler()


def _run_ingestion_tick() -> None:
    try:
        result = IngestionService().run_all_users()
        logger.info("Scheduled ingestion tick finished: %s", result)
    except Exception:
        logger.exception("Scheduled ingestion tick failed; will retry on the next tick")


def start() -> None:
    _scheduler.add_job(
        _run_ingestion_tick,
        trigger=IntervalTrigger(minutes=TICK_MINUTES),
        id=JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Ingestion scheduler started: ticking every %d minute(s)", TICK_MINUTES)


def shutdown() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
