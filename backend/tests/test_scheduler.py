from datetime import timedelta

import pytest

from app.ingestion import scheduler


@pytest.fixture(autouse=True)
def _stop_scheduler_after_test():
    yield
    scheduler.shutdown()


def test_start_adds_ingestion_job_with_configured_interval(tmp_db):
    scheduler.start()

    job = scheduler._scheduler.get_job(scheduler.JOB_ID)
    assert job is not None
    assert job.trigger.interval == timedelta(hours=4)  # tmp_db's default poll_interval_hours


def test_reschedule_updates_interval_while_running(tmp_db):
    scheduler.start()
    scheduler.reschedule(2)

    job = scheduler._scheduler.get_job(scheduler.JOB_ID)
    assert job.trigger.interval == timedelta(hours=2)


def test_reschedule_is_a_noop_when_scheduler_not_running(tmp_db):
    # e.g. a settings update landing before the scheduler has been started.
    scheduler.reschedule(3)  # must not raise
    assert scheduler._scheduler.running is False


def test_shutdown_stops_a_running_scheduler(tmp_db):
    scheduler.start()
    assert scheduler._scheduler.running is True

    scheduler.shutdown()

    assert scheduler._scheduler.running is False


def test_shutdown_is_a_noop_when_not_running(tmp_db):
    scheduler.shutdown()  # must not raise even though nothing is running
    assert scheduler._scheduler.running is False
