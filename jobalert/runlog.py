"""A readable history of every run, kept next to the saved state so GitHub shows one commit per run.

One markdown table row per run, newest at the bottom, trimmed to the most recent MAX_ROWS so the file
(and the commit) stays small forever.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

from .config import ROOT, env

MAX_ROWS = 300
HEADER = [
    "# Run log",
    "",
    "| Time | Run | Took | Result | Fetched | New | Sent | Problems |",
    "| --- | --- | ---: | --- | ---: | ---: | ---: | --- |",
]


def log_path() -> Path:
    return Path(env("JOBALERT_RUNLOG") or ROOT / "data" / "runs.md")


def _run_id() -> str:
    """Links to the GitHub Actions run when there is one ("#128"), otherwise "local"."""
    run_id, number = env("GITHUB_RUN_ID"), env("GITHUB_RUN_NUMBER")
    if not run_id:
        return "local"
    repo, server = env("GITHUB_REPOSITORY"), env("GITHUB_SERVER_URL") or "https://github.com"
    label = f"#{number or run_id}"
    return f"[{label}]({server}/{repo}/actions/runs/{run_id})" if repo else label


def format_row(result, now_local: datetime, seconds: float = 0) -> str:
    stamp = now_local.strftime("%Y-%m-%d %H:%M %Z").strip()
    head = f"| {stamp} | {_run_id()} | {seconds:.0f}s"
    if result.quiet:
        return f"{head} | quiet hours, skipped | | | | |"

    live = [r for r in result.reports if not r.skipped]
    failed = sorted(r.name for r in result.reports if r.error)
    fetched = sum(r.fetched for r in live)
    new = sum(r.new for r in live)
    outcome = "first run" if result.first_run else "ok" if not failed else "ok, with problems"
    problems = "failed: " + ", ".join(failed) if failed else ""
    return f"{head} | {outcome} | {fetched} | {new} | {result.sent} | {problems} |"


def append(result, now_local: datetime, seconds: float = 0, path: Path | None = None) -> None:
    path = path or log_path()
    rows: list[str] = []
    if path.exists():
        rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("| 20")]
    rows.append(format_row(result, now_local, seconds))
    content = "\n".join(HEADER + rows[-MAX_ROWS:]) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
