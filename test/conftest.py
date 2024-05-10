from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool
from sqlmodel import SQLModel
import pytest
from httpx import AsyncClient
from repositories.user_repository import UserRepository

from main import app
from sql_app.database import get_db
import ssl
import os

async_engine = create_async_engine(
    'postgresql+asyncpg://postgres:postgres@localhost:5432/',
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
async def create_test_database():
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

@pytest.fixture(scope="module",autouse=True)
async def load_env():
    os.environ['SECRET_KEY'] = ssl.RAND_bytes(4).hex()
    print(os.environ['SECRET_KEY'])

@pytest.fixture(scope="module")
async def user_repository():
    async with TesteSessionLocal() as db:
        return UserRepository(db)


@pytest.fixture(scope="module")
async def async_client():
    async with AsyncClient(app=app, base_url="http://localhost:8000") as client:
        yield client
