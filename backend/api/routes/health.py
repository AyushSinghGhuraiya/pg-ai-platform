"""Health check endpoints for all external services."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from db.client import check_db_health
from services.llm_client import check_llm_health
from services.redis_client import check_redis_health

router = APIRouter(tags=["health"])

_VERSION = "0.1.0"


@router.get("/")
async def root() -> dict:
    return {
        "name": "PG AI Platform",
        "version": _VERSION,
        "description": "AI-powered PG/Coliving lead management",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health")
async def health_check() -> JSONResponse:
    """Aggregate health across all services."""
    now = datetime.now(timezone.utc).isoformat()

    db_result, redis_result, llm_result = (
        await check_db_health(),
        await check_redis_health(),
        await check_llm_health(),
    )

    services = {
        "database": db_result,
        "redis": redis_result,
        "llm": llm_result,
    }

    # Determine overall status
    statuses = {s["status"] for s in services.values()}
    if "unhealthy" in statuses:
        overall = "unhealthy"
        http_code = 503
    elif "unconfigured" in statuses or "degraded" in statuses:
        overall = "degraded"
        http_code = 200
    else:
        overall = "healthy"
        http_code = 200

    return JSONResponse(
        status_code=http_code,
        content={
            "status": overall,
            "timestamp": now,
            "version": _VERSION,
            "services": services,
        },
    )


@router.get("/health/db")
async def health_db() -> JSONResponse:
    result = await check_db_health()
    code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(status_code=code, content=result)


@router.get("/health/redis")
async def health_redis() -> JSONResponse:
    result = await check_redis_health()
    code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(status_code=code, content=result)


@router.get("/health/llm")
async def health_llm() -> JSONResponse:
    result = await check_llm_health()
    code = 200 if result["status"] == "healthy" else 503
    return JSONResponse(status_code=code, content=result)
