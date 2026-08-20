import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL always wins over alembic.ini's placeholder -- the real
# connection string (with credentials) lives only in .env/the environment,
# never in a committed file. See app/core/config.py for the same convention
# used by the application itself.
#
# The app and this project's own DATABASE_URL convention use a plain
# "postgresql://" scheme (what psycopg expects directly, no SQLAlchemy
# involved there) -- but SQLAlchemy's engine, which only Alembic uses, treats
# an unqualified "postgresql://" as "use psycopg2", which isn't installed
# (this project uses psycopg 3 everywhere, see requirements.txt). Rewriting
# the scheme to "postgresql+psycopg://" here tells SQLAlchemy to use psycopg 3
# instead, without needing two different env vars for the same database.
db_url = os.environ.get("DATABASE_URL")
if db_url:
    if db_url.startswith("postgresql://"):
        db_url = "postgresql+psycopg://" + db_url[len("postgresql://") :]
    config.set_main_option("sqlalchemy.url", db_url)

# No ORM models in this project -- repositories are hand-written SQL via
# psycopg (see app/db/database.py). Migrations are plain SQL through
# op.execute()/op.create_table(), so there's no metadata to autogenerate
# against; `alembic revision --autogenerate` will not produce anything useful
# here, migrations are written by hand.
target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
