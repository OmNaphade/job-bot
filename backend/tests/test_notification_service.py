import pytest
import requests

import app.ingestion.services.notification_service as notification_service_module
from app.ingestion.services.notification_service import NotificationService
from app.models.job import Job
from app.models.notification_settings import NotificationSettings


def _job(id: int, link: str = None) -> Job:
    return Job(
        id=id,
        title=f"Backend Engineer {id}",
        company="Acme",
        location="Remote",
        link=link or f"https://example.com/jobs/{id}",
        source="test",
    )


def _telegram_settings() -> NotificationSettings:
    return NotificationSettings(telegram_bot_token="fake-token", telegram_chat_id="fake-chat")


def test_send_with_no_jobs_does_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(notification_service_module.requests, "post", lambda *a, **k: calls.append(1))

    assert NotificationService(_telegram_settings()).send([]) == []
    assert calls == []


def test_send_skips_when_no_channel_configured(monkeypatch):
    calls = []
    monkeypatch.setattr(notification_service_module.requests, "post", lambda *a, **k: calls.append(1))

    assert NotificationService(NotificationSettings()).send([_job(1)]) == []
    assert calls == []


def test_send_returns_delivered_ids_on_success(monkeypatch):
    class _FakeResponse:
        def raise_for_status(self):
            pass

    monkeypatch.setattr(notification_service_module.requests, "post", lambda *a, **k: _FakeResponse())

    jobs = [_job(1), _job(2)]
    delivered = NotificationService(_telegram_settings()).send(jobs)

    assert delivered == [1, 2]


def test_send_returns_empty_when_telegram_request_fails(monkeypatch):
    def _raise(*args, **kwargs):
        raise requests.RequestException("boom")

    monkeypatch.setattr(notification_service_module.requests, "post", _raise)

    assert NotificationService(_telegram_settings()).send([_job(1)]) == []


def test_partial_batch_failure_keeps_already_delivered_ids(monkeypatch):
    """Regression test: a Telegram digest can span multiple messages. If a
    later chunk fails to send, jobs already delivered in an earlier chunk
    must still count as delivered -- only the jobs in the failed/unreached
    chunk should be left pending for the next run's retry."""
    service = NotificationService(_telegram_settings())
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


def test_send_delivers_to_slack_and_discord_when_configured(monkeypatch):
    settings = NotificationSettings(
        slack_webhook_url="https://hooks.slack.test/abc",
        discord_webhook_url="https://discord.test/webhooks/abc",
    )

    calls = []

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        return _FakeResponse()

    monkeypatch.setattr(notification_service_module.requests, "post", _fake_post)

    delivered = NotificationService(settings).send([_job(1)])

    assert delivered == [1]
    urls = {url for url, _ in calls}
    assert urls == {"https://hooks.slack.test/abc", "https://discord.test/webhooks/abc"}
    slack_payload = next(payload for url, payload in calls if url == "https://hooks.slack.test/abc")
    discord_payload = next(payload for url, payload in calls if url == "https://discord.test/webhooks/abc")
    assert "text" in slack_payload
    assert "content" in discord_payload


def test_send_reports_delivered_when_only_one_of_multiple_channels_succeeds(monkeypatch):
    """A job must still count as delivered (and not retried later) if at least
    one configured channel got it through, even if another channel is down."""
    settings = NotificationSettings(
        slack_webhook_url="https://hooks.slack.test/abc",
        discord_webhook_url="https://discord.test/webhooks/abc",
    )

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, json=None, timeout=None):
        if "discord" in url:
            raise requests.RequestException("discord is down")
        return _FakeResponse()

    monkeypatch.setattr(notification_service_module.requests, "post", _fake_post)

    delivered = NotificationService(settings).send([_job(1)])

    assert delivered == [1]


def test_discord_channel_chunks_at_its_own_lower_limit(monkeypatch):
    settings = NotificationSettings(discord_webhook_url="https://discord.test/webhooks/abc")

    service = NotificationService(settings)
    jobs = [_job(1), _job(2)]
    header_len = len(f"\U0001f514 {len(jobs)} new job match(es)\n\n")
    line_len = len(service._format_job(jobs[0]))
    # Forces exactly one job per Discord message, same technique the Telegram
    # partial-failure test above uses for MAX_MESSAGE_LENGTH.
    monkeypatch.setattr(notification_service_module, "DISCORD_MAX_MESSAGE_LENGTH", header_len + line_len)

    calls = []

    class _FakeResponse:
        def raise_for_status(self):
            pass

    def _fake_post(url, json=None, timeout=None):
        calls.append(json)
        return _FakeResponse()

    monkeypatch.setattr(notification_service_module.requests, "post", _fake_post)

    delivered = service.send(jobs)

    assert delivered == [1, 2]
    assert len(calls) == 2
