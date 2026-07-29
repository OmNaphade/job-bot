import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings

DB_PATH = Path(settings.db_path)


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT NOT NULL,
                link TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                posted_at TEXT
            )
            """
        )
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
        connection.execute(
            """
            INSERT OR IGNORE INTO ingestion_settings
                (id, enable_rss_sources, enable_linkedin_alerts, enable_naukri_alerts, allow_direct_scraping, poll_interval_hours)
            VALUES (1, 0, 0, 0, 0, 4)
            """
        )


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
