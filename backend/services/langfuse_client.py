"""
LangFuse observability client (v4 SDK).
Auto-instruments LiteLLM when configured.

Usage:
    from services.langfuse_client import observe, propagate_trace_context
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator, Optional

from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

# Module-level client singleton (v4 uses get_client() but we cache it here too)
_langfuse: Optional[Any] = None


def init_langfuse() -> None:
    """Configure LangFuse and wire it into LiteLLM. Call once at startup."""
    global _langfuse

    if not settings.langfuse_configured:
        log.warning("langfuse_skip", reason="LANGFUSE keys not set")
        return

    # Set env vars — LiteLLM and the @observe decorator both read these
    os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
    os.environ["LANGFUSE_HOST"] = settings.langfuse_host

    try:
        from langfuse import get_client
        import litellm

        _langfuse = get_client()

        # Auto-instrument every litellm call
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

        log.info("langfuse_initialized", host=settings.langfuse_host)
    except Exception as exc:
        log.error("langfuse_init_failed", error=str(exc))
        _langfuse = None


def flush_langfuse() -> None:
    """Flush pending events. Call at shutdown to avoid dropped traces."""
    if _langfuse is not None:
        try:
            _langfuse.flush()
            log.info("langfuse_flushed")
        except Exception as exc:
            log.warning("langfuse_flush_failed", error=str(exc))


def get_langfuse() -> Optional[Any]:
    """Return the LangFuse client, or None if not configured."""
    return _langfuse


def is_active() -> bool:
    return _langfuse is not None


# ── Context helpers ────────────────────────────────────────────────────────────

@contextmanager
def propagate_trace_context(
    trace_name: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    metadata: Optional[dict] = None,
) -> Generator[None, None, None]:
    """
    Context manager that sets trace-level attributes for all observations
    created inside it (including LiteLLM auto-instrumented calls).

    Usage:
        with propagate_trace_context("whatsapp_conversation", user_id=phone, session_id=conv_id):
            result = await llm_complete(prompt)
    """
    if not is_active():
        yield
        return

    try:
        from langfuse import propagate_attributes

        with propagate_attributes(
            trace_name=trace_name,
            user_id=user_id,
            session_id=session_id,
            tags=tags or [],
            metadata=metadata or {},
        ):
            yield
    except ImportError:
        # Langfuse v3 fallback — propagate_attributes not available
        yield
    except Exception as exc:
        log.warning("langfuse_propagate_failed", error=str(exc))
        yield


# ── observe decorator re-export ────────────────────────────────────────────────

def observe(name: Optional[str] = None, as_type: Optional[str] = None) -> Any:
    """
    Decorator that wraps a function in a LangFuse span.
    No-ops if LangFuse is not configured.

    Usage:
        @observe(name="resolve_location")
        async def resolve_location(text: str) -> dict: ...
    """
    def _noop_decorator(fn: Any) -> Any:
        return fn

    if not is_active():
        return _noop_decorator

    try:
        from langfuse import observe as _lf_observe

        kwargs: dict = {}
        if name:
            kwargs["name"] = name
        if as_type:
            kwargs["as_type"] = as_type
        return _lf_observe(**kwargs)
    except Exception:
        return _noop_decorator


def score_trace(
    trace_id: str,
    name: str,
    value: float,
    data_type: str = "NUMERIC",
    comment: Optional[str] = None,
) -> None:
    """Post a score to an existing trace (e.g. after user feedback)."""
    if not is_active():
        return
    try:
        _langfuse.create_score(  # type: ignore[union-attr]
            trace_id=trace_id,
            name=name,
            value=value,
            data_type=data_type,
            comment=comment,
        )
    except Exception as exc:
        log.warning("langfuse_score_failed", trace_id=trace_id, error=str(exc))


def get_trace_url(trace_id: str) -> str:
    """Return a direct link to the trace in the LangFuse dashboard."""
    host = settings.langfuse_host.rstrip("/")
    return f"{host}/trace/{trace_id}"
