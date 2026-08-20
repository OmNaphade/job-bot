"""Initial Postgres schema, ported from the legacy SQLite database.

Every table below mirrors backend/app/db/database.py's old CREATE TABLE
statements 1:1, with three deliberate upgrades now that Postgres has real
transactional DDL (SQLite did not, which is why the old code accumulated a
long list of _migrate_add_x() functions instead of writing one correct
schema):
  - INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL
  - TEXT timestamps -> TIMESTAMPTZ
  - 0/1 INTEGER booleans -> real BOOLEAN
  - declarative-only FKs -> enforced REFERENCES ... ON DELETE CASCADE

Also adds the two new tables (resume_profiles, resume_upload_events) and the
jobs.embedding column needed for resume-based job matching -- see
bot_docs/ARCHITECTURE.md for the matching design.

Revision ID: 0001
Revises:
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE users (
            id SERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )

    # embedding is nullable and backfilled asynchronously (see
    # EmbeddingService) -- a job row is fully usable for keyword-based
    # alerting before it ever gets embedded for matching.
    op.execute(
        """
        CREATE TABLE jobs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT NOT NULL,
            link TEXT NOT NULL,
            source TEXT NOT NULL,
            posted_at TEXT,
            notified_at TIMESTAMPTZ,
            logo_url TEXT,
            embedding vector(768),
            embedding_model TEXT,
            embedded_at TIMESTAMPTZ,
            UNIQUE(user_id, link)
        )
        """
    )
    op.execute("CREATE INDEX idx_jobs_user_id ON jobs(user_id)")
    # No ANN index (IVFFlat/HNSW) yet -- brute-force cosine scan over a few
    # thousand rows is fast enough at this project's scale and avoids
    # IVFFlat's "pick `lists` based on table size, REINDEX as it grows"
    # upkeep. Revisit once `jobs` exceeds roughly 50k rows.

    op.execute(
        """
        CREATE TABLE preferences (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            keyword TEXT NOT NULL,
            kind TEXT NOT NULL DEFAULT 'include',
            location TEXT,
            UNIQUE(user_id, keyword, kind)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ingestion_settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            enable_rss_sources BOOLEAN NOT NULL DEFAULT false,
            enable_linkedin_alerts BOOLEAN NOT NULL DEFAULT false,
            enable_naukri_alerts BOOLEAN NOT NULL DEFAULT false,
            enable_indeed_alerts BOOLEAN NOT NULL DEFAULT false,
            allow_direct_scraping BOOLEAN NOT NULL DEFAULT false,
            poll_interval_hours INTEGER NOT NULL DEFAULT 4
        )
        """
    )

    op.execute(
        """
        CREATE TABLE notification_settings (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            telegram_bot_token TEXT,
            telegram_chat_id TEXT,
            slack_webhook_url TEXT,
            discord_webhook_url TEXT
        )
        """
    )

    op.execute(
        """
        CREATE TABLE processed_alert_emails (
            message_id TEXT NOT NULL,
            source TEXT NOT NULL,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            processed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (message_id, source, user_id)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE ingestion_runs (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            started_at TIMESTAMPTZ NOT NULL,
            finished_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL,
            fetched_count INTEGER NOT NULL DEFAULT 0,
            matched_count INTEGER NOT NULL DEFAULT 0,
            new_count INTEGER NOT NULL DEFAULT 0,
            delivered_count INTEGER NOT NULL DEFAULT 0,
            error_message TEXT
        )
        """
    )

    # One active resume profile per user -- reupload replaces it (UPSERT),
    # same singleton-per-user pattern as ingestion_settings/notification_settings
    # above. The original PDF is never stored (see ResumeService) -- only the
    # extracted text, structured profile, and embedding.
    op.execute(
        """
        CREATE TABLE resume_profiles (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            resume_text TEXT NOT NULL,
            profile_json JSONB NOT NULL,
            embedding vector(768) NOT NULL,
            embedding_model TEXT NOT NULL,
            source_filename TEXT,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )

    # Append-only so the daily upload cap (ResumeService) can be computed as
    # COUNT(*) WHERE uploaded_at > now() - interval '1 day' without a shared
    # counter racing under concurrent requests.
    op.execute(
        """
        CREATE TABLE resume_upload_events (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX idx_resume_upload_events_user_time ON resume_upload_events(user_id, uploaded_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS resume_upload_events")
    op.execute("DROP TABLE IF EXISTS resume_profiles")
    op.execute("DROP TABLE IF EXISTS ingestion_runs")
    op.execute("DROP TABLE IF EXISTS processed_alert_emails")
    op.execute("DROP TABLE IF EXISTS notification_settings")
    op.execute("DROP TABLE IF EXISTS ingestion_settings")
    op.execute("DROP TABLE IF EXISTS preferences")
    op.execute("DROP TABLE IF EXISTS jobs")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS users")
