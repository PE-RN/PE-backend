import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv, find_dotenv
from httpx import ASGITransport, AsyncClient
import pytest
from repositories.auth_repository import AuthRepository
from repositories.user_repository import UserRepository
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

load_dotenv(find_dotenv())

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or "postgresql+asyncpg://postgres:postgres@localhost:5433/atlas"
TEST_SYNC_DATABASE_URL = os.getenv("TEST_SYNC_DATABASE_URL") or "postgresql+psycopg2://postgres:postgres@localhost:5433/atlas"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["SYNC_DATABASE_URL"] = TEST_SYNC_DATABASE_URL

from main import app
from sql_app.database import get_db

async_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TesteSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Dependency
async def get_local_db():
    db = TesteSessionLocal()
    try:
        yield db
    finally:
        await db.close()

app.dependency_overrides[get_db] = get_local_db


@pytest.fixture(scope="session", autouse=True)
def apply_test_migrations():
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_SYNC_DATABASE_URL)
    command.upgrade(config, "head")


@pytest.fixture(scope="module")
async def user_repository():
    async with TesteSessionLocal() as db:
        return UserRepository(db)


@pytest.fixture(scope="module")
async def auth_repository():
    async with TesteSessionLocal() as db:
        return AuthRepository(db)


@pytest.fixture(scope="module")
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost:8000") as client:
        yield client
