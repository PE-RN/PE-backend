from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

async_engine = create_async_engine(
    getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:cd4bCgACc5a15eddEF22FG5eGeA1adAa@roundhouse.proxy.rlwy.net:32842/atlas')
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession
)

engine = create_engine(
    getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:admin@172.18.208.1:5432/platenergias'),
    connect_args={"check_same_thread": False}
)
SyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


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

# Dependency
def get_engine():
    return create_engine(getenv('SYNC_DATABASE_URL'))
