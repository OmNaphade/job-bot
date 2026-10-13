"""Public Telegram job channels, read through their web preview (https://t.me/s/<channel>).

No login or API needed: any public channel has this read-only preview. Many Indian job channels
post fresher/off-campus roles here long before they reach the big portals. Each post becomes one
job; the first line is the title and the post text is matched against your include keywords.
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ..models import Job
from ..util import get, parse_dt
from .base import Source


class TelegramChannel(Source):
    def __init__(self, channel: str) -> None:
        self.channel = channel.lstrip("@")
        self.name = f"telegram:{self.channel}"

    def fetch(self) -> list[Job]:
        return parse_channel(get(f"https://t.me/s/{self.channel}").text, self.channel, self.name)


def parse_channel(markup: str, channel: str, source_name: str) -> list[Job]:
    soup = BeautifulSoup(markup, "html.parser")
    jobs = []
    for message in soup.select("div.tgme_widget_message"):
        body = message.select_one(".tgme_widget_message_text")
        post = message.get("data-post")
        if not body or not post:
            continue
        for br in body.find_all("br"):
            br.replace_with("\n")
        text = body.get_text()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            continue
        outbound = [
            a["href"] for a in body.find_all("a", href=True)
            if urlparse(a["href"]).netloc not in ("t.me", "telegram.me") and a["href"].startswith("http")
        ]
        stamp = message.select_one(".tgme_widget_message_date time")
        jobs.append(
            Job(
                title=re.sub(r"\s+", " ", lines[0])[:110],
                company=channel,
                location="",
                link=outbound[0] if outbound else f"https://t.me/{post}",
                source=source_name,
                posted_at=parse_dt(stamp.get("datetime")) if stamp else None,
                extra=" ".join(lines[1:]),
            )
        )
    return jobs


def build(channels: list[str]) -> list[Source]:
    return [TelegramChannel(c) for c in channels]
