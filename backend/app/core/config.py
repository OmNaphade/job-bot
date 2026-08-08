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

    # Shared-secret header required on every endpoint except /health when set.
    # Unset (the default) means auth is off -- fine for 127.0.0.1-only use, but
    # once the backend is bound to 0.0.0.0 for phone access (see
    # bot_docs/OPERATIONS.md), anything on the same network can otherwise reach it.
    api_key: str | None = field(default_factory=lambda: _env("API_KEY"))

    alert_email_address: str | None = field(default_factory=lambda: _env("ALERT_EMAIL_ADDRESS"))
    alert_email_app_password: str | None = field(default_factory=lambda: _env("ALERT_EMAIL_APP_PASSWORD"))
    alert_email_imap_host: str = field(default_factory=lambda: _env("ALERT_EMAIL_IMAP_HOST", "imap.gmail.com"))
    alert_email_imap_port: int = field(default_factory=lambda: int(_env("ALERT_EMAIL_IMAP_PORT", "993")))

    linkedin_alert_sender: str = field(
        default_factory=lambda: _env("LINKEDIN_ALERT_SENDER", "jobalerts-noreply@linkedin.com")
    )
    naukri_alert_sender: str = field(default_factory=lambda: _env("NAUKRI_ALERT_SENDER", "noreply@naukri.com"))
    # Indeed's job-alert sender: was alert@indeed.com historically, now sends from
    # this jobalert.indeed.com subdomain -- matching on the domain rather than the
    # full address is more resilient if the subdomain prefix changes again.
    indeed_alert_sender: str = field(default_factory=lambda: _env("INDEED_ALERT_SENDER", "jobalert.indeed.com"))

    # Gmail label folders (exposed as IMAP mailboxes) searched *in addition to* INBOX
    # for each email-alert source -- lets a Gmail filter route alerts into a label
    # without needing "skip the inbox" to also be checked. Each defaults to the label
    # name the project's own setup used; override if yours differ.
    linkedin_alert_label: str = field(default_factory=lambda: _env("LINKEDIN_ALERT_LABEL", "Linkedin Alerts"))
    naukri_alert_label: str = field(default_factory=lambda: _env("NAUKRI_ALERT_LABEL", "Naukri Alerts"))
    indeed_alert_label: str = field(default_factory=lambda: _env("INDEED_ALERT_LABEL", "Indeed Alerts"))

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

    # Unstop and Foundit both render job listings client-side (JS after page load) --
    # neither has a public feed/API. Both are instead queried via their own internal
    # endpoints (reverse-engineered, not documented; see SOURCES.md), gated by
    # `allow_direct_scraping` like the ATS sources rather than `enable_rss_sources`.
    foundit_search_queries: str | None = field(default_factory=lambda: _env("FOUNDIT_SEARCH_QUERIES"))
    foundit_search_locations: str | None = field(default_factory=lambda: _env("FOUNDIT_SEARCH_LOCATIONS"))
    foundit_search_countries: str = field(default_factory=lambda: _env("FOUNDIT_SEARCH_COUNTRIES", "India"))

    # Direct-from-company-site sources (gated by `allow_direct_scraping`, not
    # `enable_rss_sources`). Each is a comma-separated list of board tokens/slugs --
    # find them in the company's careers page URL, e.g. boards.greenhouse.io/stripe
    # -> "stripe". Empty by default; nothing is fetched until you add tokens.
    greenhouse_board_tokens: str | None = field(default_factory=lambda: _env("GREENHOUSE_BOARD_TOKENS"))
    lever_company_slugs: str | None = field(default_factory=lambda: _env("LEVER_COMPANY_SLUGS"))
    ashby_board_names: str | None = field(default_factory=lambda: _env("ASHBY_BOARD_NAMES"))

    # Evaluated and confirmed to have NO public RSS/JSON feed (login-gated, JS-rendered,
    # paywalled, or discontinued) -- see bot_docs/SOURCES.md for detail per source:
    # Naukri, LinkedIn, Indeed (RSS discontinued; all three handled instead via
    # email alerts, see below), Fiverr, Upwork (RSS discontinued, 410 Gone),
    # Remote Rocketship (Cloudflare-blocked), Eztrackr (an application tracker, not a job
    # board), Toptal, Skip The Drive, FlexJobs, Remote.co, AngelList/Wellfound, Freelancer,
    # Working Nomads (JS-rendered), SimplyHired, Stack Overflow Jobs (shut down 2022),
    # Glassdoor, Monster, CareerCloud, CareerBuilder.


settings = Settings()
