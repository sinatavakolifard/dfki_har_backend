from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
_SessionLocal = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _SessionLocal() as session:
        yield session


def get_engine():
    return _engine
