"""
PG AI Platform — FastAPI application entry point.
All service initialization and teardown happens in the lifespan context.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from config import settings
from utils.logger import RequestLoggingMiddleware, configure_logging, get_logger

log = get_logger(__name__)


def _init_sentry() -> None:
    if not settings.sentry_dsn:
        log.info("sentry_skip", reason="SENTRY_DSN not set")
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1 if settings.is_production else 1.0,
        send_default_pii=False,
    )
    log.info("sentry_initialized", env=settings.app_env)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # ── Startup ───────────────────────────────────────────────────────────────
    configure_logging(is_production=settings.is_production)
    log.info("startup_begin", env=settings.app_env)

    _init_sentry()

    # Supabase
    from db.client import init_db
    await init_db()

    # Redis
    from services.redis_client import init_redis
    await init_redis()

    # LLM (set env vars before LangFuse so LiteLLM picks them up)
    from services.llm_client import init_llm
    init_llm()

    # LangFuse (wires into LiteLLM callbacks)
    from services.langfuse_client import init_langfuse
    init_langfuse()

    # WhatsApp outbound service
    from services.whatsapp import whatsapp_service
    whatsapp_service.init()

    log.info("startup_complete", message="All services connected — PG AI Platform ready")
    print("\n" + "=" * 55)
    print("  PG AI Platform — Backend Started")
    print(f"  Env      : {settings.app_env}")
    print(f"  DB       : {'✓' if settings.db_configured else '✗ not configured'}")
    print(f"  Redis    : {'✓' if settings.redis_configured else '✗ not configured'}")
    print(f"  LLM      : {'✓' if settings.llm_configured else '✗ not configured'}")
    print(f"  LangFuse : {'✓' if settings.langfuse_configured else '✗ not configured'}")
    print(f"  Sentry   : {'✓' if settings.sentry_dsn else '✗ not configured'}")
    print(f"  WhatsApp : {'✓' if settings.whatsapp_access_token else '✗ not configured'}")
    print("=" * 55 + "\n")

    yield  # ← application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────────
    from db.client import close_db
    await close_db()

    from services.redis_client import close_redis
    await close_redis()

    from services.langfuse_client import flush_langfuse
    flush_langfuse()

    from services.whatsapp import whatsapp_service
    await whatsapp_service.close()

    log.info("shutdown_complete")


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="PG AI Platform",
    description="AI-powered PG/Coliving lead management API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# ── Middleware ────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_exception", path=request.url.path, error=str(exc), exc_info=True)
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc) if settings.is_development else ""},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
from api.routes.health import router as health_router
from api.routes.test import router as test_router
from api.webhooks.whatsapp import router as whatsapp_webhook_router
from api.routes.test_whatsapp import router as test_whatsapp_router

app.include_router(health_router)
app.include_router(test_router)
app.include_router(whatsapp_webhook_router)
app.include_router(test_whatsapp_router)
