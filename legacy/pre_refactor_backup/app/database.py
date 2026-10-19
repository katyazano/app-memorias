import os
from collections.abc import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# Load .env file automatically if present
load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5433/construction_db",
)

# Configure the async engine with pooling for production readiness
async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query debugging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# Async session factory
async_session_maker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""
    pass


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency / context helper to yield async database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
