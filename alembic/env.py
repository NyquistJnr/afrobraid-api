import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import get_settings
from app.core.database import Base

# Import every module's models so they register on Base.metadata for autogenerate.
from app.modules.auth import models as auth_models  # noqa: F401
from app.modules.bookings.calculations import models as booking_calculations_models  # noqa: F401
from app.modules.braiders import models as braiders_models  # noqa: F401
from app.modules.braiders.offerings import models as braider_offerings_models  # noqa: F401
from app.modules.braiders.portfolio import models as braider_portfolio_models  # noqa: F401
from app.modules.braiders.service_location import (
    models as braider_service_location_models,  # noqa: F401
)
from app.modules.braiders.veriff import models as veriff_models  # noqa: F401
from app.modules.platform_settings import models as platform_settings_models  # noqa: F401
from app.modules.styles import models as styles_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    # The DB URL comes from our app settings (.env), never from alembic.ini,
    # so real credentials never need to be committed there. Bypassing
    # configparser also avoids it choking on the "%" in a URL-encoded password.
    return get_settings().database_url

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
