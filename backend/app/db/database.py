import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import settings

DB_PATH = Path(settings.db_path)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                posted_at TEXT,
                notified_at TEXT
            )
            """
        )
        _migrate_add_notified_at(connection)
        _migrate_add_logo_url(connection)
        _migrate_add_user_id_to_jobs(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'include',
                location TEXT,
                UNIQUE(keyword, kind)
            )
            """
        )
        _migrate_add_user_id_to_preferences(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enable_rss_sources INTEGER NOT NULL DEFAULT 0,
                enable_linkedin_alerts INTEGER NOT NULL DEFAULT 0,
                enable_naukri_alerts INTEGER NOT NULL DEFAULT 0,
                allow_direct_scraping INTEGER NOT NULL DEFAULT 0,
                poll_interval_hours INTEGER NOT NULL DEFAULT 4
            )
            """
        )
        _migrate_add_enable_indeed_alerts(connection)
        _migrate_ingestion_settings_to_per_user(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS notification_settings (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                telegram_bot_token TEXT,
                telegram_chat_id TEXT,
                slack_webhook_url TEXT,
                discord_webhook_url TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_alert_emails (
                message_id TEXT NOT NULL,
                source TEXT NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (message_id, source)
            )
            """
        )
        _migrate_add_user_id_to_processed_alert_emails(connection)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                status TEXT NOT NULL,
                fetched_count INTEGER NOT NULL DEFAULT 0,
                matched_count INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                delivered_count INTEGER NOT NULL DEFAULT 0,
                error_message TEXT
            )
            """
        )
        _migrate_add_user_id_to_ingestion_runs(connection)


def _migrate_add_notified_at(connection: sqlite3.Connection) -> None:
    """Backfills `notified_at` for rows written before the column existed.

    Without this, every job already in the table would look "pending" and
    get re-sent to Telegram the next time the notification retry queue
    (JobRepository.list_unnotified) runs -- a mass repeat of old alerts.
    Stamping them as already-notified is safe: they were either already
    delivered under the old fire-and-forget flow, or are old enough that
    resurfacing them now would be noise, not a genuine catch-up.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
    if "notified_at" in columns:
        return
    connection.execute("ALTER TABLE jobs ADD COLUMN notified_at TEXT")
    connection.execute(
        "UPDATE jobs SET notified_at = ? WHERE notified_at IS NULL",
        (datetime.now(timezone.utc).isoformat(),),
    )


def _migrate_add_logo_url(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
    if "logo_url" in columns:
        return
    connection.execute("ALTER TABLE jobs ADD COLUMN logo_url TEXT")


def _migrate_add_user_id_to_jobs(connection: sqlite3.Connection) -> None:
    """Rescopes job dedup from globally-unique links to per-user.

    SQLite can't ALTER a UNIQUE constraint, only add columns -- changing
    `UNIQUE(link)` to `UNIQUE(user_id, link)` needs the standard SQLite
    table-rebuild dance (create the new shape, copy rows across, swap it in)
    instead of a plain ALTER TABLE ADD COLUMN. Existing rows get user_id =
    NULL (no owner yet); see bot_docs/OPERATIONS.md's "upgrading an existing
    single-user install" for the one-time manual step that assigns them to a
    real account after it signs up. NULL never collides with itself under a
    UNIQUE constraint, so this is safe even before that step runs.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()}
    if "user_id" in columns:
        return
    connection.execute(
        """
        CREATE TABLE jobs_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            link TEXT NOT NULL,
            source TEXT NOT NULL,
            posted_at TEXT,
            notified_at TEXT,
            logo_url TEXT,
            UNIQUE(user_id, link)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO jobs_new (id, user_id, title, company, location, link, source, posted_at, notified_at, logo_url)
        SELECT id, NULL, title, company, location, link, source, posted_at, notified_at, logo_url FROM jobs
        """
    )
    connection.execute("DROP TABLE jobs")
    connection.execute("ALTER TABLE jobs_new RENAME TO jobs")


def _migrate_add_user_id_to_preferences(connection: sqlite3.Connection) -> None:
    """Same table-rebuild reasoning as _migrate_add_user_id_to_jobs, applied to
    preferences' `UNIQUE(keyword, kind)` -> `UNIQUE(user_id, keyword, kind)`."""
    columns = {row[1] for row in connection.execute("PRAGMA table_info(preferences)").fetchall()}
    if "user_id" in columns:
        return
    connection.execute(
        """
        CREATE TABLE preferences_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            keyword TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'include',
            location TEXT,
            UNIQUE(user_id, keyword, kind)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO preferences_new (id, user_id, keyword, kind, location)
        SELECT id, NULL, keyword, kind, location FROM preferences
        """
    )
    connection.execute("DROP TABLE preferences")
    connection.execute("ALTER TABLE preferences_new RENAME TO preferences")


def _migrate_add_enable_indeed_alerts(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(ingestion_settings)").fetchall()}
    if "enable_indeed_alerts" in columns:
        return
    connection.execute("ALTER TABLE ingestion_settings ADD COLUMN enable_indeed_alerts INTEGER NOT NULL DEFAULT 0")


def _migrate_ingestion_settings_to_per_user(connection: sqlite3.Connection) -> None:
    """Converts the old true-singleton `ingestion_settings` (id=1, CHECK-enforced)
    into one row per user, keyed by user_id.

    Deliberately does NOT carry the old singleton row's values forward -- there's
    no real user to attribute them to yet, and re-flipping a handful of boolean
    toggles once after signing up is far cheaper than engineering a preserve-and-
    reassign path for it (unlike jobs/preferences, which hold real accumulated
    data worth keeping). A fresh per-user row is created lazily on first access
    (see IngestionSettingsRepository.get()).
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(ingestion_settings)").fetchall()}
    if "user_id" in columns:
        return
    connection.execute("DROP TABLE ingestion_settings")
    connection.execute(
        """
        CREATE TABLE ingestion_settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(id),
            enable_rss_sources INTEGER NOT NULL DEFAULT 0,
            enable_linkedin_alerts INTEGER NOT NULL DEFAULT 0,
            enable_naukri_alerts INTEGER NOT NULL DEFAULT 0,
            enable_indeed_alerts INTEGER NOT NULL DEFAULT 0,
            allow_direct_scraping INTEGER NOT NULL DEFAULT 0,
            poll_interval_hours INTEGER NOT NULL DEFAULT 4
        )
        """
    )


def _migrate_add_user_id_to_processed_alert_emails(connection: sqlite3.Connection) -> None:
    """Rebuilds to scope the dedup cache per-user (same rebuild reasoning as
    _migrate_add_user_id_to_jobs -- the primary key shape is changing).

    Old rows aren't preserved: this table is a pure dedup cache, not real user
    data, so starting it empty just means each user's next ingestion run may
    re-process a handful of already-seen alert emails once -- harmless and
    idempotent, since the resulting candidates still go through normal
    per-user job dedup. Simpler than inventing a placeholder owner for rows
    that predate any real user account.
    """
    columns = {row[1] for row in connection.execute("PRAGMA table_info(processed_alert_emails)").fetchall()}
    if "user_id" in columns:
        return
    connection.execute("DROP TABLE processed_alert_emails")
    connection.execute(
        """
        CREATE TABLE processed_alert_emails (
            message_id TEXT NOT NULL,
            source TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            processed_at TEXT NOT NULL,
            PRIMARY KEY (message_id, source, user_id)
        )
        """
    )


def _migrate_add_user_id_to_ingestion_runs(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(ingestion_runs)").fetchall()}
    if "user_id" in columns:
        return
    connection.execute("ALTER TABLE ingestion_runs ADD COLUMN user_id INTEGER")


@contextmanager
def db_session() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
