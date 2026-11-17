import asyncio
from logging.config import fileConfig

from alembic import context
from alembic.command import upgrade as upgrade_command
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.permissions import sync_model_permissions
from app.db.base import Base
from app.db.models import load_models

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importar los modelos para registrar sus tablas.
load_models()

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generar SQL sin conectarse a PostgreSQL."""
    context.configure(
        url=str(settings.database_url),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    options = config.cmd_opts
    command = getattr(options, "cmd", None)

    is_upgrade_head = (
        command is not None
        and command[0] is upgrade_command
        and getattr(options, "revision", None) == "head"
    )

    with context.begin_transaction():
        context.run_migrations()

        if is_upgrade_head:
            sync_model_permissions(connection)


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        str(settings.database_url),
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Ejecutar migraciones con conexión a PostgreSQL."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
