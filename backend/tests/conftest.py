import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from app.db import database

# Defaults to the docker-compose test database (see backend/docker-compose.yml,
# `docker compose up -d`) -- override with TEST_DATABASE_URL to point at a
# different Postgres instance (e.g. in CI).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://job_alert:job_alert@localhost:5433/job_alert_test"
)


@pytest.fixture(scope="session")
def _migrated_test_db() -> str:
    """Runs Alembic migrations once per test session against the shared test
    database, instead of once per test -- individual tests get isolation from
    each other via the savepoint-per-test wrapper in `tmp_db` below, not by
    re-creating the schema each time."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    # alembic/env.py prefers the DATABASE_URL env var over the Config object's
    # url (that's what makes plain `alembic upgrade head` work from a shell
    # with .env loaded) -- which would otherwise silently out-rank the test URL
    # set above and migrate the dev database instead. Override it for the
    # duration of this call so `command.upgrade` actually targets the test DB.
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    try:
        command.upgrade(cfg, "head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
    return TEST_DATABASE_URL


@pytest.fixture
def tmp_db(_migrated_test_db, monkeypatch):
    """Each test runs inside its own outer transaction against the already-
    migrated test database, rolled back at teardown -- this is what the old
    fresh-sqlite-file-per-test fixture achieved for SQLite, adapted for a
    shared Postgres instance (re-running migrations per test would be far
    slower for no isolation benefit).

    Nested `database.db_session()` calls from repositories become SAVEPOINTs
    via `connection.transaction()`, because that API only creates a savepoint
    when called *inside* an already-open `.transaction()` block -- the first
    call otherwise starts (and, on clean exit, commits) a real top-level
    transaction. So this fixture opens that outer block itself before handing
    control to the test, then forces a rollback of it afterwards by raising
    `psycopg.Rollback` (psycopg's documented way to roll back a specific
    `with connection.transaction():` block without the exception propagating
    any further) -- no repository code needs to know it's running in a test.
    """
    connection = psycopg.connect(_migrated_test_db, row_factory=dict_row)
    register_vector(connection)

    @contextmanager
    def _test_db_session():
        with connection.transaction():
            yield connection

    monkeypatch.setattr(database, "db_session", _test_db_session)
    try:
        with connection.transaction() as outer:
            yield connection
            raise psycopg.Rollback(outer)
    finally:
        connection.close()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The signup/login rate limiter (app/core/rate_limit.py) is a module-
    level singleton with process-wide in-memory storage -- without this, its
    counters would accumulate across the *entire* test session (every test
    file, regardless of order), since Starlette's TestClient always presents
    the same source IP. A handful of signup/login calls in one file has
    already been enough to silently eat into the limit by the time a later
    file's tests run; reset before every test so rate-limiting stays a
    property of the route under test, not of how many other tests happened
    to run first.
    """
    from app.core.rate_limit import limiter

    limiter.reset()


@pytest.fixture
def test_user(tmp_db):
    """A real persisted user, for tests that need a user_id to scope data
    against without exercising the full signup flow themselves."""
    from app.core.security import hash_password
    from app.repositories.user_repository import UserRepository

    return UserRepository().create("test@example.com", hash_password("password123"))


@pytest.fixture
def auth_headers(test_user):
    """Authorization header for `test_user`, for route tests via TestClient."""
    from app.repositories.session_repository import SessionRepository

    token = SessionRepository().create(test_user.id)
    return {"Authorization": f"Bearer {token}"}
