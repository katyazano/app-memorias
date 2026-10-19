from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Generador asíncrono para inyección de dependencias en FastAPI.
    Proporciona una sesión de base de datos SQLAlchemy por petición HTTP.
    """
    async for session in get_async_session():
        yield session
