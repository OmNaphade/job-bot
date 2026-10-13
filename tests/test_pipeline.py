from datetime import datetime, timedelta, timezone

import pytest

from jobalert import pipeline
from jobalert.notify import Telegram
from tests.test_core import FakeSource, make_job

NOW = datetime.now(timezone.utc)

CONFIG = {
    "keywords": {"include": ["python"], "exclude": ["senior"]},
    "location": {},
    "sources": {},
    "notify": {"individual_limit": 2},
    "run": {"max_age_days": 3, "first_run_limit": 2, "max_per_run": 3},
}


class FakeTelegram(Telegram):
    def __init__(self, fail=False):
        super().__init__("token", "chat")
        self.messages, self.fail = [], fail

    def send_text(self, text, *, buttons=None):
        if self.fail:
            return False
        self.messages.append(text)
        return True


@pytest.fixture
def env_setup(monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")
    monkeypatch.setenv("JOBALERT_STATE", str(tmp_path / "state.json"))
    holder = {"telegram": FakeTelegram(), "sources": []}
    monkeypatch.setattr(pipeline, "Telegram", lambda *_: holder["telegram"])
    monkeypatch.setattr(pipeline, "build_sources", lambda _config: holder["sources"])
    return holder


def jobs(n, **kw):
    return [make_job(f"Python Developer {i}", link=f"https://x.test/{i}", company=f"Co{i}", **kw) for i in range(n)]


def test_first_run_sends_best_few_and_silently_remembers_rest(env_setup):
    env_setup["sources"] = [FakeSource(jobs(5))]
    result = pipeline.run(CONFIG)
    assert result.first_run and result.sent == 2
    assert "live" in env_setup["telegram"].messages[0]

    # Second run: nothing new, nothing sent -- the 3 quietly remembered jobs are not alerted later.
    env_setup["telegram"].messages.clear()
    again = pipeline.run(CONFIG)
    assert not again.first_run and again.sent == 0 and env_setup["telegram"].messages == []


def test_only_new_jobs_are_sent_and_cap_carries_over(env_setup):
    env_setup["sources"] = [FakeSource(jobs(1))]
    pipeline.run(CONFIG)  # first run seeds state

    env_setup["sources"] = [FakeSource(jobs(1) + [make_job(f"Python Dev {i}", link=f"https://y.test/{i}", company=f"N{i}") for i in range(5)])]
    first = pipeline.run(CONFIG)
    assert first.sent == 3  # max_per_run
    second = pipeline.run(CONFIG)
    assert second.sent == 2  # the overflow arrives next run, nothing lost or repeated


def test_duplicates_across_sources_are_sent_once(env_setup):
    env_setup["sources"] = [FakeSource(jobs(1)), FakeSource([make_job("Python Developer 0", company="Co0", link="https://other.test/z")], name="b")]
    result = pipeline.run(CONFIG)
    assert len(result.to_send) == 1


def test_failed_delivery_is_retried_next_run(env_setup):
    env_setup["sources"] = [FakeSource(jobs(1))]
    pipeline.run(CONFIG)  # seed
    env_setup["sources"] = [FakeSource([make_job("Python Engineer", link="https://z.test/1", company="Z")])]

    env_setup["telegram"] = FakeTelegram(fail=True)
    assert pipeline.run(CONFIG).sent == 0
    env_setup["telegram"] = FakeTelegram()
    assert pipeline.run(CONFIG).sent == 1


def test_broken_source_does_not_stop_others_and_is_reported(env_setup):
    class Broken(FakeSource):
        def fetch(self):
            raise RuntimeError("blocked")

    env_setup["sources"] = [Broken(name="broken"), FakeSource(jobs(1))]
    result = pipeline.run(CONFIG)
    errors = {r.name: r.error for r in result.reports}
    assert errors["broken"] == "blocked" and errors["fake"] is None
    assert result.sent == 1


def test_repeated_source_failure_sends_one_warning(env_setup):
    class Broken(FakeSource):
        def fetch(self):
            raise RuntimeError("blocked")

    env_setup["sources"] = [Broken(name="linkedin"), FakeSource(jobs(1))]
    for _ in range(pipeline.FAILURE_ALERT_STREAK + 3):
        pipeline.run(CONFIG)
    warnings = [m for m in env_setup["telegram"].messages if "failed" in m]
    assert len(warnings) == 1


def test_dry_run_sends_and_saves_nothing(env_setup, tmp_path):
    env_setup["sources"] = [FakeSource(jobs(2, posted_at=NOW - timedelta(hours=1)))]
    result = pipeline.run(CONFIG, dry_run=True)
    assert len(result.to_send) == 2
    assert env_setup["telegram"].messages == []
    assert not (tmp_path / "state.json").exists()


class DetailSource(FakeSource):
    """Thin search results (like LinkedIn): the keyword/experience check needs the job page."""

    needs_detail = True

    def __init__(self, jobs, pages):
        super().__init__(jobs, name="thin")
        self.pages, self.opened = pages, []

    def enrich(self, job):
        self.opened.append(job.title)
        job.extra, job.min_exp = self.pages[job.title]


DETAIL_CONFIG = {
    **CONFIG,
    "keywords": {"include": ["java", "spring boot"], "exclude": [], "generic_titles": ["associate engineer"]},
    "run": {**CONFIG["run"], "max_experience_years": 1, "max_detail_fetches": 2},
}


def test_description_decides_for_thin_sources_and_rejections_are_remembered(env_setup):
    jobs_ = [
        make_job("Associate Engineer", link="https://t.test/1", company="A", location="Pune"),
        make_job("Associate Engineer", link="https://t.test/2", company="B", location="Pune"),
        make_job("Associate Engineer", link="https://t.test/3", company="C", location="Pune"),
    ]
    pages = {"Associate Engineer": ("Java Spring Boot services", 3.0)}  # asks for 3 yrs
    source = DetailSource(jobs_, pages)
    env_setup["sources"] = [FakeSource([make_job("Java Developer", link="https://ok.test/1", company="Z")], name="plain"), source]
    pipeline.run(DETAIL_CONFIG)
    assert len(source.opened) == 2  # capped at 2 page reads per run; the third job waits

    pipeline.run(DETAIL_CONFIG)
    assert len(source.opened) == 3  # only the deferred job was opened; the two rejected ones were remembered
    pipeline.run(DETAIL_CONFIG)
    assert len(source.opened) == 3  # nothing left to read


def test_good_description_is_alerted(env_setup):
    job = make_job("Associate Engineer", link="https://t.test/9", company="Q", location="Pune")
    source = DetailSource([job], {"Associate Engineer": ("Java and Spring Boot, freshers welcome", 0.0)})
    env_setup["sources"] = [source]
    result = pipeline.run(DETAIL_CONFIG)
    assert [j.title for j in result.to_send] == ["Associate Engineer"]


def test_throttled_source_sits_out_runs_that_come_too_soon(env_setup):
    class Slow(FakeSource):
        min_interval_minutes = 60

    slow = Slow(jobs(1), name="slow")
    env_setup["sources"] = [slow]
    calls = []
    original = slow.fetch
    slow.fetch = lambda: calls.append(1) or original()

    pipeline.run(CONFIG)
    second = pipeline.run(CONFIG)
    assert len(calls) == 1  # the second run was within the hour, so no request was made
    assert second.reports[0].skipped


# ---------------------------------------------------------------- quiet hours, daily summary

def test_quiet_hours_window_including_overnight_wrap():
    at = lambda hour: datetime(2026, 10, 13, hour, 17)  # noqa: E731
    day = {"start": 0, "end": 7}
    assert pipeline.in_quiet_hours(at(1), day) and pipeline.in_quiet_hours(at(6), day)
    assert not pipeline.in_quiet_hours(at(7), day) and not pipeline.in_quiet_hours(at(23), day)
    night = {"start": 23, "end": 6}
    assert pipeline.in_quiet_hours(at(23), night) and pipeline.in_quiet_hours(at(2), night)
    assert not pipeline.in_quiet_hours(at(12), night)
    assert not pipeline.in_quiet_hours(at(3), None)


def test_run_during_quiet_hours_does_nothing(env_setup, monkeypatch):
    env_setup["sources"] = [FakeSource(jobs(2))]
    monkeypatch.setattr(pipeline, "in_quiet_hours", lambda *_: True)
    result = pipeline.run(CONFIG)
    assert result.quiet and env_setup["telegram"].messages == []
    # ...but a manual run (or dry-run) ignores quiet hours
    assert not pipeline.run(CONFIG, dry_run=True).quiet


def test_daily_summary_is_sent_once_after_the_summary_hour(env_setup):
    config = {**CONFIG, "notify": {**CONFIG["notify"], "daily_summary_hour": 0, "timezone": "UTC"}}
    env_setup["sources"] = [FakeSource(jobs(1))]
    pipeline.run(config)
    summaries = [m for m in env_setup["telegram"].messages if "Daily summary" in m]
    assert len(summaries) == 1 and "Jobs sent: 1" in summaries[0] and "Fake" not in summaries[0]

    pipeline.run(config)
    assert len([m for m in env_setup["telegram"].messages if "Daily summary" in m]) == 1  # not repeated that day


def test_no_summary_when_not_configured(env_setup):
    env_setup["sources"] = [FakeSource(jobs(1))]
    pipeline.run(CONFIG)
    assert not [m for m in env_setup["telegram"].messages if "Daily summary" in m]
