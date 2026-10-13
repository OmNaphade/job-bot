import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .models import Job

RETENTION_DAYS = 45


class State:
    """Everything remembered between runs, in one small JSON file.

    seen:      job link / dedup keys already alerted on (-> ISO timestamp, pruned after 45 days)
    failures:  consecutive failed runs per source
    alerted:   sources we've already warned about during the current failure streak
    initialized: False until a run has actually fetched something, so the "first run" flood
               protection still applies if the very first run happens while every source is down
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.seen: dict[str, str] = {}
        self.failures: dict[str, int] = {}
        self.alerted: set[str] = set()
        self.last_fetch: dict[str, str] = {}
        self.initialized = False
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return  # a corrupt state file behaves like a first run rather than crashing every run
        self.seen = dict(data.get("seen", {}))
        self.failures = {k: int(v) for k, v in data.get("failures", {}).items()}
        self.alerted = set(data.get("alerted", []))
        self.last_fetch = dict(data.get("last_fetch", {}))
        self.initialized = bool(data.get("initialized", bool(self.seen)))

    def minutes_since_fetch(self, source_name: str) -> float | None:
        stamp = self.last_fetch.get(source_name)
        if not stamp:
            return None
        return (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds() / 60

    def mark_fetched(self, source_name: str) -> None:
        self.last_fetch[source_name] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    def has_seen(self, job: Job) -> bool:
        return job.link_key in self.seen or job.dedup_key in self.seen

    def mark_seen(self, job: Job) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.seen[job.link_key] = stamp
        self.seen[job.dedup_key] = stamp

    def save(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat(timespec="seconds")
        self.seen = {key: stamp for key, stamp in self.seen.items() if stamp >= cutoff}
        payload = {
            "initialized": self.initialized,
            "seen": self.seen,
            "failures": self.failures,
            "alerted": sorted(self.alerted),
            "last_fetch": self.last_fetch,
            # Changes once a day, so the Actions state branch gets a daily commit even when idle; that
            # repo activity is what stops GitHub from pausing the schedule after 60 quiet days.
            "last_run": datetime.now(timezone.utc).date().isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a crash mid-write can't leave a half-written state file.
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=0, sort_keys=True)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
