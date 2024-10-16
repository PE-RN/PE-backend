from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool
from sqlmodel import SQLModel
import pytest
from httpx import ASGITransport, AsyncClient
from repositories.user_repository import UserRepository
from repositories.auth_repository import AuthRepository
from dotenv import load_dotenv, find_dotenv

from main import app
from sql_app.database import get_db

async_engine = create_async_engine(
    'postgresql+asyncpg://postgres:cd4bCgACc5a15eddEF22FG5eGeA1adAa@roundhouse.proxy.rlwy.net:32842/atlas',
    poolclass=StaticPool,
)
TesteSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession)


# Dependency
async def get_local_db():
    db = TesteSessionLocal()
    try:
        yield db
    finally:
        await db.close()

app.dependency_overrides[get_db] = get_local_db


@pytest.fixture(scope="module", autouse=True)
async def load_do_env():
    load_dotenv(find_dotenv())


@pytest.fixture(scope="module", autouse=True)
async def create_test_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    await async_engine.dispose(close=False)


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
