import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    app_name: str = "Job Alert API"
    db_path: str = "job_alert.db"

    telegram_bot_token: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN"))
    telegram_chat_id: str | None = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID"))

    alert_email_address: str | None = field(default_factory=lambda: os.getenv("ALERT_EMAIL_ADDRESS"))
    alert_email_app_password: str | None = field(default_factory=lambda: os.getenv("ALERT_EMAIL_APP_PASSWORD"))
    alert_email_imap_host: str = field(default_factory=lambda: os.getenv("ALERT_EMAIL_IMAP_HOST", "imap.gmail.com"))
    alert_email_imap_port: int = field(default_factory=lambda: int(os.getenv("ALERT_EMAIL_IMAP_PORT", "993")))

    linkedin_alert_sender: str = field(
        default_factory=lambda: os.getenv("LINKEDIN_ALERT_SENDER", "jobalerts-noreply@linkedin.com")
    )
    naukri_alert_sender: str = field(default_factory=lambda: os.getenv("NAUKRI_ALERT_SENDER", "noreply@naukri.com"))

    # Verified, publicly-published RSS feeds -- no scraping, no guessed endpoints.
    weworkremotely_feed_url: str | None = field(
        default_factory=lambda: os.getenv(
            "WEWORKREMOTELY_FEED_URL", "https://weworkremotely.com/categories/remote-programming-jobs.rss"
        )
    )
    himalayas_feed_url: str | None = field(
        default_factory=lambda: os.getenv("HIMALAYAS_FEED_URL", "https://himalayas.app/jobs/rss")
    )

    # Unstop/Foundit render job listings client-side (JS after page load) -- their real API
    # endpoint isn't discoverable via a plain HTTP fetch and hasn't been guessed at here.
    # Find it via the portal's search page (DevTools -> Network -> XHR) and set it below if you want it.
    unstop_feed_url: str | None = field(default_factory=lambda: os.getenv("UNSTOP_FEED_URL"))
    foundit_feed_url: str | None = field(default_factory=lambda: os.getenv("FOUNDIT_FEED_URL"))


settings = Settings()
