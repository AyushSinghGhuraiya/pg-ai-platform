"""
Structured logging via structlog.
JSON output in production, pretty console output in development.
Usage: from utils.logger import get_logger; log = get_logger(__name__)
"""

from __future__ import annotations

import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_var.get() or "no-request"


def _add_module_name(logger: Any, method: str, event_dict: dict) -> dict:
    """Safe version of add_logger_name that works with PrintLogger."""
    name = getattr(logger, "name", None) or getattr(logger, "_name", None)
    if name:
        event_dict["logger"] = name
    return event_dict


def configure_logging(is_production: bool = False) -> None:
    """Call once at startup to configure structlog globally."""
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        _add_module_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(10),  # DEBUG = 10
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=False,  # False so configure_logging changes take effect
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Injects a unique request_id into every log line for that request."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        request_id = str(uuid.uuid4())[:8]
        _request_id_var.set(request_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        log = get_logger("http")
        log.info("request_started")

        start = time.perf_counter()
        response: Any = None
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            log.error("request_failed", error=str(exc))
            raise
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000)
            status = getattr(response, "status_code", 0)
            log.info("request_finished", status_code=status, duration_ms=duration_ms)
