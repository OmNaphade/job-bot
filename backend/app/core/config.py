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

    # Postgres connection string, e.g. postgresql://user:pass@host:5432/job_alert.
    # No default -- every environment (local dev via docker-compose, tests, both
    # VMs) must set this explicitly rather than silently falling back to
    # something that looks plausible but points at the wrong database.
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL") or "")

    # Required on POST /auth/signup when set (unset = open signup). Every other
    # route requires a real per-user session token instead (see
    # app/core/security.py) -- this only gates account creation itself, since
    # that route can't require a session token that doesn't exist yet. Stops a
    # publicly-reachable deployment from letting anyone create an account.
    signup_invite_code: str | None = field(default_factory=lambda: _env("SIGNUP_INVITE_CODE"))

    # Session token lifetime (see app/core/security.py::create_session).
    session_ttl_days: int = field(default_factory=lambda: int(_env("SESSION_TTL_DAYS", "30")))

    # CORS origin allowed to call the API cross-origin (native Flutter builds --
    # Windows/Android/iOS -- hit the API directly rather than same-origin
    # through nginx the way the web build does). "*" is the permissive local-
    # dev default; set to the real deployed origin (e.g.
    # https://job-alert-app.duckdns.org) once this is reachable beyond
    # 127.0.0.1 -- see app/middleware.py and bot_docs/OPERATIONS.md.
    allowed_origin: str = field(default_factory=lambda: _env("ALLOWED_ORIGIN", "*"))

    # Google Gemini API key (aistudio.google.com, free tier) -- used for both
    # resume structured-extraction (app/ai/gemini_client.py) and embeddings
    # (resume profiles + job postings, for GET /matches). No default: resume
    # upload fails loudly with a clear error if this is unset, rather than
    # every call quietly failing deep inside the AI client.
    google_api_key: str | None = field(default_factory=lambda: _env("GOOGLE_API_KEY"))
    # Model ids are env-driven so they're bumpable without a code change.
    gemini_extraction_model: str = field(default_factory=lambda: _env("GEMINI_EXTRACTION_MODEL", "gemini-2.5-flash"))
    # 768-dim to match the `vector(768)` columns in 0001_initial_schema.py.
    gemini_embedding_model: str = field(default_factory=lambda: _env("GEMINI_EMBEDDING_MODEL", "text-embedding-004"))
    # Per-user resume uploads/day -- protects the free Gemini quota from being
    # exhausted by one account re-uploading in a loop (see ResumeService).
    resume_upload_daily_cap: int = field(default_factory=lambda: int(_env("RESUME_UPLOAD_DAILY_CAP", "5")))

    # Per-IP limits on account creation/login (see app/core/rate_limit.py) --
    # signup is open (no invite code required by default now), so these are
    # what stands between a public deployment and someone scripting account
    # creation or password-guessing. `limits`-library syntax, e.g. "5/hour".
    signup_rate_limit: str = field(default_factory=lambda: _env("SIGNUP_RATE_LIMIT", "5/hour"))
    login_rate_limit: str = field(default_factory=lambda: _env("LOGIN_RATE_LIMIT", "10/15minute"))

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

    # Tier A: documented, apiKey-based aggregator APIs -- gated by `enable_rss_sources`,
    # same trust tier as the RSS/JSON feeds above (officially published, no scraping).
    # Arbeitnow needs no key at all; the other three self-disable in the registry if
    # their required key/query env vars are unset (same pattern as Foundit's location gate).
    adzuna_app_id: str | None = field(default_factory=lambda: _env("ADZUNA_APP_ID"))
    adzuna_app_key: str | None = field(default_factory=lambda: _env("ADZUNA_APP_KEY"))
    adzuna_country: str = field(default_factory=lambda: _env("ADZUNA_COUNTRY", "in"))
    adzuna_search_queries: str | None = field(default_factory=lambda: _env("ADZUNA_SEARCH_QUERIES"))

    jooble_api_key: str | None = field(default_factory=lambda: _env("JOOBLE_API_KEY"))
    jooble_search_queries: str | None = field(default_factory=lambda: _env("JOOBLE_SEARCH_QUERIES"))
    jooble_location: str | None = field(default_factory=lambda: _env("JOOBLE_LOCATION"))

    themuse_api_key: str | None = field(default_factory=lambda: _env("THEMUSE_API_KEY"))
    themuse_categories: str | None = field(default_factory=lambda: _env("THEMUSE_CATEGORIES"))

    # Notification channels (Telegram/Slack/Discord) are per-user, stored in the
    # `notification_settings` table -- see app/models/notification_settings.py --
    # not global env vars.

    # Evaluated and confirmed to have NO public RSS/JSON feed (login-gated, JS-rendered,
    # paywalled, or discontinued) -- see bot_docs/SOURCES.md for detail per source:
    # Naukri, LinkedIn, Indeed (RSS discontinued; all three handled instead via
    # email alerts, see below), Fiverr, Upwork (RSS discontinued, 410 Gone),
    # Remote Rocketship (Cloudflare-blocked), Eztrackr (an application tracker, not a job
    # board), Toptal, Skip The Drive, FlexJobs, Remote.co, AngelList/Wellfound, Freelancer,
    # Working Nomads (JS-rendered), SimplyHired, Stack Overflow Jobs (shut down 2022),
    # Glassdoor, Monster, CareerCloud, CareerBuilder.


settings = Settings()
