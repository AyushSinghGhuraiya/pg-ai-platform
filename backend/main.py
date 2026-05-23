"""
PG AI Platform — FastAPI application entry point.
"""

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

# ── Sentry (only when DSN is configured) ─────────────────────────────────────
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.1,
    )

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="PG AI Platform",
    description="AI-powered PG/Coliving lead management API",
    version="0.1.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    print("=" * 50)
    print("PG AI Platform - Backend Started")
    print(f"  Environment : {settings.app_env}")
    print(f"  Supabase    : {'✓ configured' if settings.supabase_url else '✗ missing'}")
    print(f"  Redis       : {settings.effective_redis_url}")
    print("=" * 50)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    print("PG AI Platform - Backend Shutting Down")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "service": "PG AI Platform",
        "version": "0.1.0",
        "status": "running",
        "environment": settings.app_env,
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "environment": settings.app_env}
