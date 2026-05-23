"""
Upstash Redis async client — REST-based (works without TCP Redis port).
Singleton pattern managed by FastAPI lifespan.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from upstash_redis.asyncio import Redis

from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

_redis: Optional[Redis] = None


async def init_redis() -> None:
    """Create the Redis client. Call once in lifespan startup."""
    global _redis

    if not settings.redis_configured:
        log.warning("redis_skip", reason="UPSTASH_REDIS_REST_URL or TOKEN not set")
        return

    try:
        _redis = Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
        )
        # Verify connection with a PING
        pong = await _redis.ping()
        log.info("redis_connected", url=settings.upstash_redis_rest_url, ping=pong)
    except Exception as exc:
        log.error("redis_init_failed", error=str(exc))
        _redis = None  # don't crash the app, just degrade gracefully


async def close_redis() -> None:
    log.info("redis_shutdown")


def get_redis() -> Redis:
    """Return the Redis client. Raises if not initialized."""
    if _redis is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis


def _is_ready() -> bool:
    return _redis is not None


# ── Helper functions ──────────────────────────────────────────────────────────

async def cache_set(key: str, value: Any, ttl: int = 300) -> bool:
    """Set a value with optional TTL in seconds. Auto-serializes to JSON."""
    if not _is_ready():
        return False
    try:
        serialized = json.dumps(value) if not isinstance(value, (str, int, float)) else value
        await _redis.set(key, serialized, ex=ttl)  # type: ignore[union-attr]
        return True
    except Exception as exc:
        log.warning("cache_set_failed", key=key, error=str(exc))
        return False


async def cache_get(key: str) -> Any:
    """Get a value, auto-deserializing JSON. Returns None on miss or error."""
    if not _is_ready():
        return None
    try:
        raw = await _redis.get(key)  # type: ignore[union-attr]
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    except Exception as exc:
        log.warning("cache_get_failed", key=key, error=str(exc))
        return None


async def cache_delete(key: str) -> bool:
    """Delete a key. Returns True if deleted."""
    if not _is_ready():
        return False
    try:
        count = await _redis.delete(key)  # type: ignore[union-attr]
        return count > 0
    except Exception as exc:
        log.warning("cache_delete_failed", key=key, error=str(exc))
        return False


async def cache_exists(key: str) -> bool:
    """Check if a key exists."""
    if not _is_ready():
        return False
    try:
        return bool(await _redis.exists(key))  # type: ignore[union-attr]
    except Exception as exc:
        log.warning("cache_exists_failed", key=key, error=str(exc))
        return False


async def check_redis_health() -> dict:
    """Health check — PING and measure latency."""
    if not _is_ready():
        return {"status": "unconfigured", "error": "Redis not initialized"}

    start = time.perf_counter()
    try:
        pong = await _redis.ping()  # type: ignore[union-attr]
        latency_ms = round((time.perf_counter() - start) * 1000)
        return {"status": "healthy", "latency_ms": latency_ms, "ping": str(pong)}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000)
        log.error("redis_health_check_failed", error=str(exc))
        return {"status": "unhealthy", "latency_ms": latency_ms, "error": str(exc)}
