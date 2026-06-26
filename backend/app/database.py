from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.database_url:
            raise RuntimeError("DATABASE_URL is not set. Configure it in .env")
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.environment == "development",
            connect_args={"timeout": 15, "ssl": "require"},
        )
    return _engine


def get_session():
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    return _async_session


class Base(DeclarativeBase):
    pass


async def get_db():
    session = get_session()
    async with session() as s:
        try:
            yield s
        finally:
            await s.close()
