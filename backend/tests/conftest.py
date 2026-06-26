import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator

from httpx import AsyncClient, ASGITransport
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.routers.auth_utils import verify_public_access
from app.main import app

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ADMIN_KEY", "test-admin-key")
os.environ.setdefault("PUBLIC_API_KEY", "")

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "")
USE_SQLITE = "sqlite" in TEST_DB_URL or not TEST_DB_URL


def _patch_pg_types():
    from sqlalchemy import types as sa_types

    @sa_types.TypeEngine.compiles(ARRAY, "sqlite")
    def compile_array_sqlite(type_, compiler, **kw):
        return compiler.process(sa_types.Text())

    @sa_types.TypeEngine.compiles(JSONB, "sqlite")
    def compile_jsonb_sqlite(type_, compiler, **kw):
        return compiler.process(sa_types.JSON())

    @sa_types.TypeEngine.compiles(PG_UUID, "sqlite")
    def compile_uuid_sqlite(type_, compiler, **kw):
        return compiler.process(sa_types.String(36))


def _get_test_url():
    if USE_SQLITE:
        _patch_pg_types()
        return "sqlite+aiosqlite:///./test.db"
    return TEST_DB_URL


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    url = _get_test_url()
    e = create_async_engine(url, echo=False)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield e
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await e.dispose()
    if USE_SQLITE and os.path.exists("test.db"):
        os.remove("test.db")


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session, engine) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[verify_public_access] = lambda: True

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
