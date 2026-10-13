import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from .config import ROOT, env
from .filters import JobFilter
from .models import Job
from .notify import Telegram, format_summary, source_label
from .sources import build_sources
from .sources.base import Source
from .store import State
from .util import FetchError

log = logging.getLogger(__name__)

# Warn on Telegram once a source has failed this many runs in a row.
FAILURE_ALERT_STREAK = 3
HOT_SCORE = 8


@dataclass
class SourceReport:
    name: str
    fetched: int = 0
    new: int = 0
    error: Optional[str] = None
    skipped: str = ""


@dataclass
class RunResult:
    reports: list[SourceReport] = field(default_factory=list)
    to_send: list[Job] = field(default_factory=list)
    sent: int = 0
    first_run: bool = False
    quiet: bool = False
    rejected: dict[str, int] = field(default_factory=dict)


def state_path(config: dict) -> Path:
    return Path(env("JOBALERT_STATE") or config["run"].get("state_file") or ROOT / "data" / "state.json")


def fetch_all(sources: list[Source], workers: int = 8) -> tuple[list[tuple[Source, list[Job]]], list[SourceReport]]:
    def one(source: Source) -> tuple[Source, list[Job], SourceReport]:
        report = SourceReport(source.name)
        try:
            jobs = source.fetch()
            report.fetched = len(jobs)
            return source, jobs, report
        except Exception as exc:  # one broken source must never stop the others
            log.warning("%s failed: %s", source.name, exc)
            report.error = str(exc)[:200]
            return source, [], report

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, sources))
    return [(s, jobs) for s, jobs, _ in results], [r for _, _, r in results]


def in_quiet_hours(now_local: datetime, quiet: Optional[dict]) -> bool:
    """True when `now_local` falls in [start, end) hours, e.g. start 0 / end 7 = midnight to 7am."""
    if not quiet:
        return False
    start, end = int(quiet.get("start", 0)), int(quiet.get("end", 0))
    if start == end:
        return False
    hour = now_local.hour
    return start <= hour < end if start < end else hour >= start or hour < end


def run(config: dict, *, dry_run: bool = False, only: Optional[str] = None) -> RunResult:
    run_cfg = config["run"]
    notify_cfg = config["notify"]
    now_local = datetime.now(ZoneInfo(notify_cfg.get("timezone", "Asia/Kolkata")))
    # Manual runs (workflow_dispatch), --only and --dry-run are you looking at the bot, so they ignore quiet hours.
    manual = dry_run or bool(only) or env("GITHUB_EVENT_NAME") == "workflow_dispatch"
    if not manual and in_quiet_hours(now_local, notify_cfg.get("quiet_hours")):
        log.info("quiet hours (%s local): skipping this run, anything new is sent at the first run after", now_local.strftime("%H:%M"))
        return RunResult(quiet=True)

    state = State(state_path(config))
    job_filter = JobFilter(config)
    telegram = Telegram(env("TELEGRAM_BOT_TOKEN"), env("TELEGRAM_CHAT_ID"))
    if not dry_run and not telegram.configured:
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID are not set (see .env.example).")

    sources = build_sources(config)
    if only:
        sources = [s for s in sources if only.lower() in s.name.lower()]
    if not sources:
        raise SystemExit("No sources are enabled/configured. Check config.yaml and your .env.")

    result = RunResult(first_run=not state.initialized)
    # Throttled sources (LinkedIn) sit out runs that come too soon after their last fetch. Skipped when
    # you ask for a source by name or dry-run, since you're explicitly looking at it.
    due, skipped = [], []
    for source in sources:
        age = state.minutes_since_fetch(source.name)
        if source.min_interval_minutes and age is not None and age < source.min_interval_minutes and not (dry_run or only):
            skipped.append(SourceReport(source.name, skipped=f"ran {age:.0f}m ago"))
        else:
            due.append(source)
    fetched, result.reports = fetch_all(due)
    result.reports += skipped
    reports = {r.name: r for r in result.reports}

    candidates: list[Job] = []
    batch_keys: set[str] = set()
    pending: list[tuple[Source, Job]] = []  # jobs whose description still has to be read

    def reject(reason: str) -> None:
        result.rejected[reason] = result.rejected.get(reason, 0) + 1

    def accept(source: Source, job: Job) -> None:
        batch_keys.update((job.link_key, job.dedup_key))
        job.score = job_filter.score(job)
        reports[source.name].new += 1
        candidates.append(job)

    def duplicate(job: Job) -> bool:
        return state.has_seen(job) or job.link_key in batch_keys or job.dedup_key in batch_keys

    for source, jobs in fetched:
        for job in jobs:
            if duplicate(job):
                continue
            thin = source.needs_detail and source.wants_detail(job)
            verdict = job_filter.check(job, source, final=not thin)
            if not verdict.keep:
                reject(verdict.reason)
            elif thin:
                pending.append((source, job))
            else:
                accept(source, job)

    # Second pass for thin sources (LinkedIn): open each survivor's page and judge it on its description.
    # Done after every other source so a job already found elsewhere isn't fetched again, newest first,
    # and capped per run; whatever is left over stays unseen and is handled on the next run.
    pending.sort(key=lambda sj: sj[1].posted_at.timestamp() if sj[1].posted_at else 0, reverse=True)
    detail_cap = int(run_cfg.get("max_detail_fetches", 25))
    deadline = time.monotonic() + float(run_cfg.get("detail_time_budget_seconds", 150))
    fetched_details = consecutive_errors = 0
    for source, job in pending:
        if duplicate(job):
            continue
        # Stop at the cap, after three refusals in a row (blocked), or when the time budget is spent.
        if fetched_details >= detail_cap or consecutive_errors >= 3 or time.monotonic() > deadline:
            continue
        fetched_details += 1
        try:
            source.enrich(job)
            consecutive_errors = 0
        except FetchError as exc:
            consecutive_errors += 1
            log.warning("%s: could not read job page: %s", source.name, exc)
            continue
        verdict = job_filter.check(job, source)
        if verdict.keep:
            accept(source, job)
        else:
            reject(verdict.reason)
            if not dry_run:
                state.mark_seen(job)  # remember the rejection so this page isn't fetched again every run

    candidates.sort(key=lambda j: (j.score, j.posted_at.timestamp() if j.posted_at else 0), reverse=True)

    if result.first_run:
        # Nothing is remembered yet, so everything looks new. Alert on the best few and quietly
        # remember the rest, otherwise the first run would flood the chat.
        limit = int(run_cfg.get("first_run_limit", 10))
        to_send = candidates[:limit]
        silent = candidates[limit:]
    else:
        limit = int(run_cfg.get("max_per_run", 40))
        to_send, silent = candidates[:limit], []  # the rest stay unseen and go out next run
    result.to_send = to_send

    if dry_run:
        return result

    delivered = _deliver(telegram, to_send, notify_cfg, first_run=result.first_run, silent=len(silent))
    for job in delivered + silent:
        state.mark_seen(job)
    result.sent = len(delivered)
    _record_stats(state, now_local, delivered)
    for report in result.reports:
        if report.error is None and not report.skipped:
            state.mark_fetched(report.name)
    state.initialized = state.initialized or any(r.error is None for r in result.reports)

    _track_failures(state, result.reports, telegram)
    summary_hour = notify_cfg.get("daily_summary_hour")
    if summary_hour is not None and now_local.hour >= int(summary_hour) and not state.stats.get("summarized"):
        if telegram.send_text(format_summary(state.stats, state.failures)):
            state.stats["summarized"] = True
    state.save()
    return result


def _record_stats(state: State, now_local: datetime, delivered: list[Job]) -> None:
    today = now_local.date().isoformat()
    if state.stats.get("date") != today:
        state.stats = {"date": today, "runs": 0, "sent": 0, "by_source": {}, "summarized": False}
    state.stats["runs"] += 1
    state.stats["sent"] += len(delivered)
    for job in delivered:
        label = source_label(job.source).split(" (")[0]
        state.stats["by_source"][label] = state.stats["by_source"].get(label, 0) + 1


def _deliver(telegram: Telegram, jobs: list[Job], notify_cfg: dict, *, first_run: bool, silent: int) -> list[Job]:
    if first_run:
        note = "✅ <b>Job alert is live.</b> Here are the best matches right now; newer ones will arrive as they appear."
        if silent:
            note += f"\n(+{silent} older matches saved quietly so you aren't flooded.)"
        telegram.send_text(note)
    if not jobs:
        return []

    individual = int(notify_cfg.get("individual_limit", 8))
    hot = int(notify_cfg.get("hot_score", HOT_SCORE))
    delivered: list[Job] = []
    for job in jobs[:individual]:
        if telegram.send_job(job, hot=job.score >= hot):
            delivered.append(job)
        else:
            return delivered  # Telegram is failing; leave the rest unseen so they retry next run
    if len(jobs) > individual:
        delivered.extend(telegram.send_digest(jobs[individual:]))
    return delivered


def _track_failures(state: State, reports: list[SourceReport], telegram: Telegram) -> None:
    for report in reports:
        if report.skipped:
            continue
        if report.error is None:
            state.failures.pop(report.name, None)
            state.alerted.discard(report.name)
            continue
        state.failures[report.name] = state.failures.get(report.name, 0) + 1
        if state.failures[report.name] >= FAILURE_ALERT_STREAK and report.name not in state.alerted:
            if telegram.send_text(
                f"⚠️ <b>{source_label(report.name)}</b> has failed {state.failures[report.name]} runs in a row.\n"
                f"Last error: <code>{_escape(report.error)}</code>"
            ):
                state.alerted.add(report.name)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")[:300]
