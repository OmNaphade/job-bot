from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import settings

# Schema is owned by Alembic (see backend/alembic/) now that Postgres has real
# transactional DDL -- there is no init_db()/CREATE TABLE IF NOT EXISTS dance
# here the way there was for SQLite. Run `alembic upgrade head` before the app
# ever starts (see deploy/oci_deploy_db.sh, which is the only place migrations
# run in production -- see bot_docs/ARCHITECTURE.md for why).
_pool: ConnectionPool | None = None


def _configure_connection(connection: psycopg.Connection) -> None:
    register_vector(connection)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # Conservative sizing -- VM2 (or VM1, whichever holds this process) has
        # only 1GB RAM total, shared with Postgres itself and/or the ingestion
        # worker. See bot_docs/OPERATIONS.md for the full footprint discussion.
        _pool = ConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=5,
            kwargs={"row_factory": dict_row},
            configure=_configure_connection,
        )
    return _pool


@contextmanager
def db_session() -> Iterator[psycopg.Connection]:
    with get_pool().connection() as connection:
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
