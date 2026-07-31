import dataclasses

import pytest
import requests

import app.ingestion.services.notification_service as notification_service_module
from app.ingestion.services.notification_service import NotificationService
from app.models.job import Job


def _job(id: int, link: str = None) -> Job:
    return Job(
        id=id,
        title=f"Backend Engineer {id}",
        company="Acme",
        location="Remote",
        link=link or f"https://example.com/jobs/{id}",
        source="test",
    )


@pytest.fixture
def configured_settings(monkeypatch):
    """Points the module's `settings` singleton at a Telegram-configured copy
    without mutating the real (frozen) settings object other tests rely on."""
    configured = dataclasses.replace(
        notification_service_module.settings, telegram_bot_token="fake-token", telegram_chat_id="fake-chat"
    )
    monkeypatch.setattr(notification_service_module, "settings", configured)
    return configured


def test_send_with_no_jobs_does_nothing(configured_settings, monkeypatch):
    calls = []
    monkeypatch.setattr(notification_service_module.requests, "post", lambda *a, **k: calls.append(1))

    assert NotificationService().send([]) == []
    assert calls == []


def test_send_skips_when_telegram_not_configured(monkeypatch):
    unconfigured = dataclasses.replace(
        notification_service_module.settings, telegram_bot_token=None, telegram_chat_id=None
    )
    monkeypatch.setattr(notification_service_module, "settings", unconfigured)
    calls = []
    monkeypatch.setattr(notification_service_module.requests, "post", lambda *a, **k: calls.append(1))

    assert NotificationService().send([_job(1)]) == []
    assert calls == []


def test_send_returns_delivered_ids_on_success(configured_settings, monkeypatch):
    class _FakeResponse:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(notification_service_module.requests, "post", lambda *a, **k: _FakeResponse())

    jobs = [_job(1), _job(2)]
    delivered = NotificationService().send(jobs)

    assert delivered == [1, 2]


def test_send_returns_empty_when_telegram_request_fails(configured_settings, monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(notification_service_module.requests, "post", _raise)

    assert NotificationService().send([_job(1)]) == []


def test_partial_batch_failure_keeps_already_delivered_ids(configured_settings, monkeypatch):
    """Regression test: a Telegram digest can span multiple messages. If a
    later chunk fails to send, jobs already delivered in an earlier chunk
    must still count as delivered -- only the jobs in the failed/unreached
    chunk should be left pending for the next run's retry."""
    service = NotificationService()
    jobs = [_job(1), _job(2)]

    header_len = len(f"\U0001f514 {len(jobs)} new job match(es)\n\n")
    line_len = len(service._format_job(jobs[0]))
    # Forces exactly one job per message batch: after job 1 fills a batch to
    # capacity, job 2's line can't fit and starts a fresh batch.
    monkeypatch.setattr(notification_service_module, "MAX_MESSAGE_LENGTH", header_len + line_len)

    call_count = {"n": 0}

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _FakeResponse()
        raise requests.RequestException("second chunk failed")

    monkeypatch.setattr(notification_service_module.requests, "post", _fake_post)

    delivered = service.send(jobs)

    assert delivered == [1]
    assert call_count["n"] == 2
