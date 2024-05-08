from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from os import getenv


async_engine = create_async_engine(
    getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:postgres@localhost:5432/atlas')
)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine, class_=AsyncSession)


async def init_db():
    """Create the database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


# Dependency
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()
