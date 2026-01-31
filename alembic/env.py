"""Alembic migration environment."""

import sys
print("Alembic env.py: Starting imports...", file=sys.stderr, flush=True)

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

print("Alembic env.py: Importing models...", file=sys.stderr, flush=True)
# Import models for autogenerate
from src.bot_ebooks.models import Base
print("Alembic env.py: Importing config...", file=sys.stderr, flush=True)
from src.bot_ebooks.config import get_settings

config = context.config
print("Alembic env.py: Getting settings...", file=sys.stderr, flush=True)
settings = get_settings()

# Get sync database URL (replace asyncpg with psycopg2 for migrations)
db_url = settings.async_database_url
# Convert async URL to sync URL for alembic
sync_db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
print(f"Alembic env.py: DB URL configured (host hidden)", file=sys.stderr, flush=True)

config.set_main_option("sqlalchemy.url", sync_db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    print("Alembic env.py: Creating engine...", file=sys.stderr, flush=True)
    connectable = create_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    print("Alembic env.py: Connecting to database...", file=sys.stderr, flush=True)
    with connectable.connect() as connection:
        print("Alembic env.py: Configuring context...", file=sys.stderr, flush=True)
        context.configure(connection=connection, target_metadata=target_metadata)

        print("Alembic env.py: Running migrations...", file=sys.stderr, flush=True)
        with context.begin_transaction():
            context.run_migrations()
        print("Alembic env.py: Migrations completed!", file=sys.stderr, flush=True)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
