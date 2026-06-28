import asyncio
import inspect
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler, Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import Base, get_engine
from app.routers import profiles, orgs, search, stats, auth, admin, pricing, blog, investor


# Patch slowapi's deprecated iscoroutinefunction check
if not hasattr(asyncio, "iscoroutinefunction"):
    asyncio.iscoroutinefunction = inspect.iscoroutinefunction


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response


class RequestBodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > 1_048_576:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large (max 1MB)"},
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = None
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # Add role column to public.users if it doesn't exist
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND table_schema='public' AND column_name='role'")
            )
            if not result.scalar():
                await conn.execute(text("ALTER TABLE public.users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))
                print("Added 'role' column to users table", flush=True)
            else:
                print("Role column already exists in public.users", flush=True)
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        print(f"DB init: {e}", flush=True)
    yield
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass


async def production_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app = FastAPI(title="Sporafind API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.environment == "production":
    app.add_exception_handler(Exception, production_exception_handler)

app.add_middleware(RequestBodySizeMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Key", "X-Api-Key"],
)

app.include_router(profiles.router)
app.include_router(orgs.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(pricing.router)
app.include_router(blog.router)
app.include_router(investor.router)


@app.get("/")
async def root():
    return {"app": "Sporafind API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}