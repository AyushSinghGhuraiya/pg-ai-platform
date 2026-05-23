"""
LangFuse observability client.
Auto-instruments LiteLLM when configured.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

_langfuse: Optional[Any] = None


def init_langfuse() -> None:
    """Configure LangFuse and wire it into LiteLLM. Call at startup."""
    global _langfuse

    if not settings.langfuse_configured:
        log.warning("langfuse_skip", reason="LANGFUSE keys not set")
        return

    # Set env vars so LiteLLM auto-picks them up
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host

    try:
        from langfuse import Langfuse

        _langfuse = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

        # Wire LangFuse into LiteLLM globally
        import litellm

        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        log.info("langfuse_initialized", host=settings.langfuse_host)
    except Exception as exc:
        log.error("langfuse_init_failed", error=str(exc))
        _langfuse = None


def flush_langfuse() -> None:
    """Flush pending events to LangFuse. Call at shutdown."""
    if _langfuse is not None:
        try:
            _langfuse.flush()
            log.info("langfuse_flushed")
        except Exception as exc:
            log.warning("langfuse_flush_failed", error=str(exc))


def get_langfuse() -> Optional[Any]:
    return _langfuse


def trace(name: str, metadata: dict | None = None) -> Any:
    """Start a LangFuse trace. Returns the trace object or None."""
    if _langfuse is None:
        return None
    try:
        return _langfuse.trace(name=name, metadata=metadata or {})
    except Exception:
        return None
