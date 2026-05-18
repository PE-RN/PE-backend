from os import getenv

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

database_url = getenv('DATABASE_URL', "postgresql+asyncpg://postgres:postgres@postgresql:5432/atlas")
disable_db_pool = getenv("DATABASE_DISABLE_POOL", "false").lower() in {"1", "true", "yes"}

engine_kwargs = {}
if disable_db_pool:
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs["pool_size"] = 20
    engine_kwargs["max_overflow"] = 10

async_engine = create_async_engine(database_url, **engine_kwargs)
SessionLocal = async_sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession)


async def init_db():
    """Create the database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: None)
        # await conn.run_sync(SQLModel.metadata.create_all)


# Dependency
async def get_db():
    async with SessionLocal() as db:
        yield db
