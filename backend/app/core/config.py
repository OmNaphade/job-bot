import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    """os.getenv, but treats a set-but-empty value as unset too.

    GitHub Actions sets an env var to "" (not unset) when it's wired to a
    ${{ secrets.X }} reference for a secret that doesn't exist -- plain
    os.getenv(name, default) would return "" instead of falling back.
    """
    return os.getenv(name) or default


@dataclass(frozen=True)
class Settings:
    app_name: str = "Job Alert API"
    db_path: str = "job_alert.db"

    telegram_bot_token: str | None = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str | None = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID"))

    alert_email_address: str | None = field(default_factory=lambda: _env("ALERT_EMAIL_ADDRESS"))
    alert_email_app_password: str | None = field(default_factory=lambda: _env("ALERT_EMAIL_APP_PASSWORD"))
    alert_email_imap_host: str = field(default_factory=lambda: _env("ALERT_EMAIL_IMAP_HOST", "imap.gmail.com"))
    alert_email_imap_port: int = field(default_factory=lambda: int(_env("ALERT_EMAIL_IMAP_PORT", "993")))

    linkedin_alert_sender: str = field(
        default_factory=lambda: _env("LINKEDIN_ALERT_SENDER", "jobalerts-noreply@linkedin.com")
    )
    naukri_alert_sender: str = field(default_factory=lambda: _env("NAUKRI_ALERT_SENDER", "noreply@naukri.com"))

    # Verified, publicly-published RSS feeds -- no scraping, no guessed endpoints.
    weworkremotely_feed_url: str | None = field(
        default_factory=lambda: _env(
            "WEWORKREMOTELY_FEED_URL", "https://weworkremotely.com/categories/remote-programming-jobs.rss"
        )
    )
    himalayas_feed_url: str | None = field(
        default_factory=lambda: _env("HIMALAYAS_FEED_URL", "https://himalayas.app/jobs/rss")
    )
    remotive_feed_url: str | None = field(
        default_factory=lambda: _env("REMOTIVE_FEED_URL", "https://remotive.com/remote-jobs/feed")
    )
    nodesk_feed_url: str | None = field(
        default_factory=lambda: _env("NODESK_FEED_URL", "https://nodesk.co/remote-jobs/index.xml")
    )
    jobspresso_feed_url: str | None = field(
        default_factory=lambda: _env("JOBSPRESSO_FEED_URL", "https://jobspresso.co/feed/")
    )
    # RemoteOK's RSS feed (remoteok.com/remote-jobs.rss) was discontinued (410 Gone);
    # their JSON API is the current, publicly-documented replacement.
    remoteok_api_url: str | None = field(default_factory=lambda: _env("REMOTEOK_API_URL", "https://remoteok.com/api"))

    # Unstop/Foundit render job listings client-side (JS after page load) -- their real API
    # endpoint isn't discoverable via a plain HTTP fetch and hasn't been guessed at here.
    # Find it via the portal's search page (DevTools -> Network -> XHR) and set it below if you want it.
    unstop_feed_url: str | None = field(default_factory=lambda: _env("UNSTOP_FEED_URL"))
    foundit_feed_url: str | None = field(default_factory=lambda: _env("FOUNDIT_FEED_URL"))

    # Evaluated and confirmed to have NO public RSS/JSON feed (login-gated, JS-rendered,
    # paywalled, or discontinued) -- see bot_docs/SOURCES.md for detail per source:
    # Naukri, LinkedIn (both handled instead via email alerts, see below),
    # Fiverr, Upwork (RSS discontinued, 410 Gone), Indeed (RSS discontinued),
    # Remote Rocketship (Cloudflare-blocked), Eztrackr (an application tracker, not a job
    # board), Toptal, Skip The Drive, FlexJobs, Remote.co, AngelList/Wellfound, Freelancer,
    # Working Nomads (JS-rendered), SimplyHired, Stack Overflow Jobs (shut down 2022),
    # Glassdoor, Monster, CareerCloud, CareerBuilder.


settings = Settings()
