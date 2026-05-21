from os import getenv
from logging.config import fileConfig

from dotenv import find_dotenv, load_dotenv
from sqlalchemy import create_engine
from sqlalchemy import pool
from sqlalchemy.engine import URL, make_url

from alembic import context

from sqlmodel import SQLModel
from sql_app.models import GroupPermissionLink, Group, Permission, TemporaryUser, User, AnonymousUser, LogsEmail, PdfFile, Video, Feedback, Geodata, GeoJsonData, PasswordResetToken

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config


def _load_environment() -> None:
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        return

    try:
        load_dotenv(dotenv_path)
    except UnicodeDecodeError:
        # Some local Windows setups still persist .env files in ANSI/latin-1.
        load_dotenv(dotenv_path, encoding="latin-1")


def _resolve_sync_database_url() -> URL:
    raw_url = (
        getenv("SYNC_DATABASE_URL")
        or getenv("DATABASE_URL")
        or "postgresql+psycopg2://postgres:postgres@postgresql:5432/atlas"
    )
    url = make_url(str(raw_url))

    drivername = url.drivername
    if drivername in {"postgres", "postgresql"}:
        return url.set(drivername="postgresql+psycopg2")

    if drivername.startswith("postgresql+") and drivername != "postgresql+psycopg2":
        return url.set(drivername="postgresql+psycopg2")

    return url


_load_environment()
SYNC_DATABASE_URL = _resolve_sync_database_url()
config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL.render_as_string(hide_password=False))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = SQLModel.metadata

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
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(SYNC_DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
