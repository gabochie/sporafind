from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from slowapi import _rate_limit_exceeded_handler, Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import get_engine
from app.routers import profiles, orgs, search, stats, auth, admin, pricing, blog


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = None
    try:
        engine = get_engine()
    except Exception as e:
        print(f"DB engine init skipped: {e}")
    yield
    if engine is not None:
        try:
            await engine.dispose()
        except Exception:
            pass


app = FastAPI(title="Sporafind API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
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


@app.get("/")
async def root():
    return {"app": "Sporafind API", "version": "0.1.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0"}
