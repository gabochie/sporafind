from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

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
            print(f"[DB] Connection error: {e}", flush=True)
            raise
        finally:
            await s.close()
