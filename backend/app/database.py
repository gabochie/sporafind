import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.logger import logger

_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        url = settings.database_url
        if not url:
            raise RuntimeError("DATABASE_URL is not set. Configure it in .env")
        if url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        _engine = create_async_engine(
            url,
            echo=settings.environment == "development",
            connect_args={"ssl": "require", "statement_cache_size": 0},
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
        except Exception as e:
            logger.error("Database connection error", exc_info=e)
            raise
        finally:
            await s.close()


async def dispose_engine(engine=None) -> None:
    if engine is None:
        engine = _engine
    if engine is None:
        return
    try:
        await asyncio.wait_for(engine.dispose(), timeout=5.0)
        logger.info("Database engine disposed")
    except asyncio.TimeoutError:
        logger.warning("Database engine disposal timed out")
    except Exception as e:
        logger.error("Database engine disposal error", exc_info=e)
