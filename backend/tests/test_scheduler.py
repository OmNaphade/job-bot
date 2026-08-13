from datetime import timedelta

import pytest

from app.ingestion import scheduler


@pytest.fixture(autouse=True)
def _stop_scheduler_after_test():
    yield
    scheduler.shutdown()


def test_start_adds_ingestion_job_with_fixed_tick_interval(tmp_db):
    scheduler.start()

    job = scheduler._scheduler.get_job(scheduler.JOB_ID)
    assert job is not None
    assert job.trigger.interval == timedelta(minutes=scheduler.TICK_MINUTES)


def test_shutdown_stops_a_running_scheduler(tmp_db):
    scheduler.start()
    assert scheduler._scheduler.running is True

    scheduler.shutdown()

    assert scheduler._scheduler.running is False


def test_shutdown_is_a_noop_when_not_running(tmp_db):
    scheduler.shutdown()  # must not raise even though nothing is running
    assert scheduler._scheduler.running is False
