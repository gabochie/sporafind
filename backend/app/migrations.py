from sqlalchemy import text
from app.database import get_engine, Base
from app.logger import logger


async def run_migrations():
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='role'")
        )
        if not result.scalar():
            await conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
            logger.info("Added 'role' column to users table")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Migration complete")
