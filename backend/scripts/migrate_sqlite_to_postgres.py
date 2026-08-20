"""One-time migration of the legacy SQLite database (backend/job_alert.db)
into Postgres. Run once, manually, after standing up Postgres and applying
Alembic migrations (`alembic upgrade head`) but before pointing the app at
DATABASE_URL for real traffic.

Usage (from the backend/ directory, with DATABASE_URL pointing at the target
Postgres database):
    python -m scripts.migrate_sqlite_to_postgres path/to/job_alert.db

What it does:
  - Copies every row from every table, preserving primary key values (so
    sessions.user_id, jobs.user_id, etc. keep pointing at the right row)
    instead of remapping IDs.
  - Migrates in FK order: users first, then everything that references it.
  - Resets each table's SERIAL sequence afterward so the next INSERT doesn't
    collide with a migrated ID.
  - Prints a row-count comparison per table at the end -- verify these match
    before trusting the migration and cutting over.

New columns introduced for the AI features (jobs.embedding, resume_profiles,
resume_upload_events) are simply not touched here -- there's nothing to
migrate for them, they start empty. See EmbeddingService for the one-off
backfill pass that populates jobs.embedding for pre-existing rows.
"""

import sqlite3
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.core.config import settings

# (table, columns-in-insert-order) -- order matters, respects FK dependencies.
_TABLES: list[tuple[str, list[str]]] = [
    ("users", ["id", "email", "password_hash", "created_at"]),
    ("sessions", ["token", "user_id", "created_at", "expires_at"]),
    (
        "jobs",
        ["id", "user_id", "title", "company", "location", "link", "source", "posted_at", "notified_at", "logo_url"],
    ),
    ("preferences", ["id", "user_id", "keyword", "kind", "location"]),
    (
        "ingestion_settings",
        [
            "user_id",
            "enable_rss_sources",
            "enable_linkedin_alerts",
            "enable_naukri_alerts",
            "enable_indeed_alerts",
            "allow_direct_scraping",
            "poll_interval_hours",
        ],
    ),
    (
        "notification_settings",
        ["user_id", "telegram_bot_token", "telegram_chat_id", "slack_webhook_url", "discord_webhook_url"],
    ),
    ("processed_alert_emails", ["message_id", "source", "user_id", "processed_at"]),
    (
        "ingestion_runs",
        [
            "id",
            "user_id",
            "started_at",
            "finished_at",
            "status",
            "fetched_count",
            "matched_count",
            "new_count",
            "delivered_count",
            "error_message",
        ],
    ),
]

# Tables with a SERIAL id column that needs its sequence bumped past the
# highest migrated value -- singleton/composite-PK tables (ingestion_settings,
# notification_settings, processed_alert_emails) don't have one.
_SERIAL_TABLES = ["users", "jobs", "preferences", "ingestion_runs"]

# SQLite stored these as 0/1 INTEGER; the Postgres schema (0001_initial_schema)
# uses real BOOLEAN columns, which psycopg won't implicitly cast an int to --
# converted to Python bool on read so executemany() below gets a type Postgres
# actually accepts.
_BOOLEAN_COLUMNS = {
    "enable_rss_sources",
    "enable_linkedin_alerts",
    "enable_naukri_alerts",
    "enable_indeed_alerts",
    "allow_direct_scraping",
}


def _read_sqlite_rows(sqlite_path: Path, table: str, columns: list[str]) -> list[tuple]:
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    finally:
        connection.close()
    return [
        tuple(bool(row[column]) if column in _BOOLEAN_COLUMNS else row[column] for column in columns)
        for row in rows
    ]


def _migrate_table(pg_connection: psycopg.Connection, sqlite_path: Path, table: str, columns: list[str]) -> int:
    rows = _read_sqlite_rows(sqlite_path, table, columns)
    if not rows:
        return 0
    placeholders = ", ".join(["%s"] * len(columns))
    column_list = ", ".join(columns)
    with pg_connection.cursor() as cursor:
        cursor.executemany(
            f"INSERT INTO {table} ({column_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
            rows,
        )
    return len(rows)


def _reset_sequence(pg_connection: psycopg.Connection, table: str) -> None:
    with pg_connection.cursor() as cursor:
        cursor.execute(
            f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1), "
            f"(SELECT MAX(id) FROM {table}) IS NOT NULL)"
        )


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m scripts.migrate_sqlite_to_postgres path/to/job_alert.db", file=sys.stderr)
        sys.exit(1)

    sqlite_path = Path(sys.argv[1]).resolve()
    if not sqlite_path.is_file():
        print(f"No such file: {sqlite_path}", file=sys.stderr)
        sys.exit(1)

    if not settings.database_url:
        print("DATABASE_URL is not set -- point it at the target Postgres database first.", file=sys.stderr)
        sys.exit(1)

    print(f"Migrating {sqlite_path} -> {settings.database_url.split('@')[-1]}")

    with psycopg.connect(settings.database_url, row_factory=dict_row, autocommit=False) as pg_connection:
        migrated_counts: dict[str, int] = {}
        for table, columns in _TABLES:
            migrated_counts[table] = _migrate_table(pg_connection, sqlite_path, table, columns)
            print(f"  {table}: {migrated_counts[table]} rows")

        for table in _SERIAL_TABLES:
            _reset_sequence(pg_connection, table)

        pg_connection.commit()

    print("\nRow-count comparison (SQLite source vs rows just inserted -- should match unless some rows already")
    print("existed in Postgres and were skipped by ON CONFLICT DO NOTHING):")
    sqlite_connection = sqlite3.connect(sqlite_path)
    try:
        for table, _ in _TABLES:
            sqlite_count = sqlite_connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            status = "OK" if sqlite_count == migrated_counts[table] else "MISMATCH -- verify manually"
            print(f"  {table}: sqlite={sqlite_count} migrated={migrated_counts[table]} [{status}]")
    finally:
        sqlite_connection.close()

    print(
        "\nDone. Verify the counts above, smoke-test the app against Postgres, then stop treating "
        "backend/job_alert.db as the source of truth (see bot_docs/OPERATIONS.md)."
    )


if __name__ == "__main__":
    main()
