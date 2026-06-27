import asyncio
import os
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.import_run import ImportRun
from app.services.importer import run_import


async def start_import(ctx: dict, nationality: str = "Ghanaian") -> dict:
    db_session = ctx["db_session"]
    import_run_id = str(uuid4())

    async with db_session() as db:
        run = ImportRun(id=import_run_id, status="queued")
        db.add(run)
        await db.commit()

    async with db_session() as db:
        await run_import(import_run_id, db)

    async with db_session() as db:
        run = await db.get(ImportRun, import_run_id)
        return {
            "id": run.id,
            "status": run.status,
            "records_imported": run.records_imported,
            "records_failed": run.records_failed,
            "orgs_imported": run.orgs_imported,
        }


async def get_import_status(ctx: dict, import_run_id: str) -> dict | None:
    db_session = ctx["db_session"]
    async with db_session() as db:
        run = await db.get(ImportRun, import_run_id)
        if not run:
            return None
        return {
            "id": run.id,
            "status": run.status,
            "records_found": run.records_found,
            "records_imported": run.records_imported,
            "records_failed": run.records_failed,
            "orgs_found": run.orgs_found,
            "orgs_imported": run.orgs_imported,
            "error_message": run.error_message,
            "started_at": str(run.started_at) if run.started_at else None,
            "completed_at": str(run.completed_at) if run.completed_at else None,
        }


async def get_db_session(database_url: str) -> async_sessionmaker:
    url = database_url
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(url, connect_args={"ssl": "require", "statement_cache_size": 0})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def startup(ctx: dict):
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    ctx["db_session"] = await get_db_session(database_url)


class WorkerSettings:
    functions = [start_import, get_import_status]
    on_startup = startup
    redis_settings = None  # set via env REDIS_URL

    @classmethod
    def from_env(cls):
        import redis.asyncio as redis
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
        cls.redis_settings = redis.from_url(redis_url)
        return cls
