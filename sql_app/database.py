from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker

#ATABASE_URL = "sqlite:///./sql_app.db"
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlas"

async_engine = create_async_engine(
    DATABASE_URL
)
SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=async_engine,class_= AsyncSession)

async def init_db():
    """Create the database tables"""
    async with async_engine.begin() as conn:
        from .models import  User, Group, LogsEmail, PdfFile, Video, Geodata 
        await conn.run_sync(SQLModel.metadata.create_all)

