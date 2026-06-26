from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import get_engine, Base
from app.routers import profiles, orgs, search, stats, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"DB init skipped: {e}")
    yield
    try:
        await engine.dispose()
    except Exception:
        pass


app = FastAPI(title="Sporafind API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router)
app.include_router(orgs.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}
