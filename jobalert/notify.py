import html
import logging
import time
from datetime import datetime, timezone
from typing import Iterator, Optional

import requests

from .models import Job

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/{method}"
_MAX_LEN = 3900  # Telegram's hard limit is 4096; leave headroom for the header.

_SOURCE_LABELS = {
    "linkedin": "LinkedIn", "naukri": "Naukri", "indeed": "Indeed", "foundit": "Foundit", "unstop": "Unstop",
    "adzuna": "Adzuna", "jooble": "Jooble", "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby",
    "weworkremotely": "WeWorkRemotely", "himalayas": "Himalayas", "remotive": "Remotive",
    "remoteok": "RemoteOK", "arbeitnow": "Arbeitnow", "jobspresso": "Jobspresso", "nodesk": "NoDesk",
    "telegram": "Telegram",
}
_SHOW_DETAIL = {"greenhouse", "lever", "ashby", "telegram"}


def source_label(source: str) -> str:
    base, _, detail = source.partition(":")
    base = base.replace("_alerts", "")
    label = _SOURCE_LABELS.get(base, base)
    return f"{label} ({detail})" if detail and base in _SHOW_DETAIL else label


def _age(posted_at: Optional[datetime]) -> str:
    if not posted_at:
        return ""
    minutes = max(0, int((datetime.now(timezone.utc) - posted_at).total_seconds() // 60))
    if minutes < 60:
        return f"{max(minutes, 1)}m ago"
    if minutes < 60 * 48:
        return f"{minutes // 60}h ago"
    return f"{minutes // 1440}d ago"


def _experience(job: Job) -> str:
    if job.min_exp is None:
        return ""
    low = f"{job.min_exp:g}"
    return f"{low}-{job.max_exp:g} yrs" if job.max_exp and job.max_exp > job.min_exp else f"{low}+ yrs"


def format_job(job: Job, *, hot: bool = False) -> str:
    esc = html.escape
    lines = [
        f"{'🔥' if hot else '💼'} <b>{esc(job.title)}</b>",
        f"🏢 {esc(job.company)}  ·  📍 {esc(job.location)}",
    ]
    facts = [part for part in (_experience(job), job.salary) if part]
    if facts:
        lines.append("🎓 " + "  ·  ".join(esc(f) for f in facts))
    age = _age(job.posted_at)
    lines.append(f"🕐 {age + '  ·  ' if age else ''}via {esc(source_label(job.source))}")
    return "\n".join(lines)


def format_digest_line(index: int, job: Job) -> str:
    where = job.location if job.location != "Unknown" else ""
    detail = " · ".join(part for part in (job.company, where, _age(job.posted_at)) if part)
    link = html.escape(job.link, quote=True)
    return f'{index}. <a href="{link}">{html.escape(job.title)}</a>\n    {html.escape(detail)}'


def chunk_digest(jobs: list[Job]) -> Iterator[tuple[list[Job], str]]:
    header = f"🔔 <b>{len(jobs)} more new job{'s' if len(jobs) != 1 else ''}</b>\n\n"
    chunk: list[Job] = []
    text = header
    for index, job in enumerate(jobs, start=1):
        line = format_digest_line(index, job) + "\n\n"
        if chunk and len(text) + len(line) > _MAX_LEN:
            yield chunk, text
            chunk, text = [], ""
        chunk.append(job)
        text += line
    if chunk:
        yield chunk, text


class Telegram:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id

    @property
    def configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def _post(self, method: str, payload: dict) -> bool:
        url = _API.format(token=self.token, method=method)
        for _ in range(3):
            try:
                response = requests.post(url, json=payload, timeout=20)
            except requests.RequestException as exc:
                # Don't log the exception text: requests includes the URL, which contains the bot token.
                log.warning("Telegram request failed (%s)", type(exc).__name__)
                time.sleep(2)
                continue
            if response.status_code == 429:
                retry_after = int(response.json().get("parameters", {}).get("retry_after", 3))
                time.sleep(min(retry_after + 1, 30))
                continue
            if response.ok:
                return True
            log.error("Telegram rejected %s: %s %s", method, response.status_code, response.text[:200])
            return False
        return False

    def send_text(self, text: str, *, buttons: Optional[list[list[dict]]] = None) -> bool:
        payload: dict = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if buttons:
            payload["reply_markup"] = {"inline_keyboard": buttons}
        return self._post("sendMessage", payload)

    def send_job(self, job: Job, *, hot: bool = False) -> bool:
        return self.send_text(format_job(job, hot=hot), buttons=[[{"text": "Apply / View ↗", "url": job.link}]])

    def send_digest(self, jobs: list[Job]) -> list[Job]:
        """Sends `jobs` as compact numbered lists split to fit Telegram's size limit.
        Returns the jobs that were actually delivered."""
        delivered: list[Job] = []
        for chunk, text in chunk_digest(jobs):
            if not self.send_text(text):
                break
            delivered.extend(chunk)
            time.sleep(0.3)
        return delivered
