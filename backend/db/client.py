"""
Supabase async client — singleton pattern, managed by FastAPI lifespan.

Two clients:
  supabase_admin  — service role key, bypasses RLS (backend operations)
  supabase_user   — anon key, respects RLS (user-context operations)
"""

from __future__ import annotations

import time
from typing import Optional

from supabase._async.client import AsyncClient
from supabase._async.client import create_client as _create_async_client

from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

# Module-level singletons
_admin_client: Optional[AsyncClient] = None
_user_client: Optional[AsyncClient] = None


async def init_db() -> None:
    """Create Supabase clients. Call once in lifespan startup."""
    global _admin_client, _user_client

    if not settings.db_configured:
        log.warning("supabase_skip", reason="SUPABASE_URL or SUPABASE_SERVICE_KEY not set")
        return

    try:
        _admin_client = await _create_async_client(
            settings.supabase_url,
            settings.supabase_service_key,
        )
        _user_client = await _create_async_client(
            settings.supabase_url,
            settings.supabase_anon_key,
        )
        log.info("supabase_connected", url=settings.supabase_url)
    except Exception as exc:
        log.error("supabase_init_failed", error=str(exc))
        raise


async def close_db() -> None:
    """No explicit close needed for supabase-py HTTP clients, but log shutdown."""
    log.info("supabase_shutdown")


def get_supabase() -> AsyncClient:
    """Return admin client (bypasses RLS). Use for all backend operations."""
    if _admin_client is None:
        raise RuntimeError("Supabase admin client not initialized. Call init_db() first.")
    return _admin_client


def get_supabase_user() -> AsyncClient:
    """Return anon client (respects RLS). Use when acting as a user."""
    if _user_client is None:
        raise RuntimeError("Supabase user client not initialized. Call init_db() first.")
    return _user_client


async def check_db_health() -> dict:
    """Quick health check — returns latency and tenant count."""
    if _admin_client is None:
        return {"status": "unconfigured", "error": "Client not initialized"}

    start = time.perf_counter()
    try:
        result = await _admin_client.table("tenants").select("id").limit(1).execute()
        latency_ms = round((time.perf_counter() - start) * 1000)
        return {
            "status": "healthy",
            "latency_ms": latency_ms,
            "tenant_rows": len(result.data),
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000)
        log.error("db_health_check_failed", error=str(exc))
        return {"status": "unhealthy", "latency_ms": latency_ms, "error": str(exc)}
