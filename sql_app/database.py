from os import getenv

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

async_engine = create_async_engine(
    getenv('DATABASE_URL', "postgresql+asyncpg://postgres:postgres@postgresql:5432/atlas"),
    pool_size=20,
    max_overflow=10
)
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession)


async def init_db():
    """Create the database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# Dependency
async def get_db():
    async with SessionLocal() as db:
        yield db
