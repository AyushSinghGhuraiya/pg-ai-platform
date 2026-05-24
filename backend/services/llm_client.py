"""
LiteLLM unified gateway for all LLM providers.

Routing:
  default        → gemini/gemini-2.0-flash (free)
  extraction     → gemini/gemini-2.0-flash (or gpt-4o-mini when key available)
  response_gen   → gemini/gemini-2.0-flash (or claude-3-5-haiku when key available)
  fallback chain → gemini → groq/llama-3.3-70b-versatile → error

Every call automatically:
  - Logs to LangFuse via litellm callback (trace_name, session_id, user_id, tags)
  - Retries through the fallback chain on rate limits
  - Returns LLMResponse with tokens, cost, latency, and trace_id for the LangFuse UI
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import litellm
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from config import settings
from utils.logger import get_logger

log = get_logger(__name__)

# ── Model aliases ─────────────────────────────────────────────────────────────
_GEMINI = "gemini/gemini-2.0-flash"
_GROQ = "groq/llama-3.3-70b-versatile"
_GPT4O_MINI = "gpt-4o-mini"
_CLAUDE_HAIKU = "claude-3-5-haiku-20241022"

_DEFAULT_MODEL = _GEMINI
_EXTRACTION_MODEL = _GPT4O_MINI if settings.openai_api_key else _GEMINI
_RESPONSE_MODEL = _CLAUDE_HAIKU if settings.anthropic_api_key else _GEMINI

# Ordered fallback chain — tried left-to-right on rate limit / unavailable
_FALLBACK_MODELS = [_GEMINI, _GROQ]


@dataclass
class LLMResponse:
    text: str
    model_used: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    trace_id: Optional[str] = None      # LangFuse trace ID — use get_trace_url() for link
    metadata: dict = field(default_factory=dict)


def init_llm() -> None:
    """Set env vars for all providers. Call once at startup."""
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    litellm.set_verbose = False  # suppress per-call logging noise

    log.info(
        "llm_configured",
        gemini=bool(settings.gemini_api_key),
        groq=bool(settings.groq_api_key),
        openai=bool(settings.openai_api_key),
        anthropic=bool(settings.anthropic_api_key),
        default_model=_DEFAULT_MODEL,
    )


def _pick_model(role: Optional[str]) -> str:
    if role == "extraction":
        return _EXTRACTION_MODEL
    if role == "response_gen":
        return _RESPONSE_MODEL
    return _DEFAULT_MODEL


def _build_langfuse_metadata(
    trace_name: Optional[str],
    trace_id: Optional[str],
    user_id: Optional[str],
    session_id: Optional[str],
    tags: Optional[list[str]],
    generation_name: Optional[str],
    extra_metadata: Optional[dict],
) -> dict:
    """
    Build the metadata dict that LiteLLM forwards to LangFuse.
    Keys are the LiteLLM→LangFuse contract:
      trace_name, trace_id, trace_user_id, trace_session_id, tags, generation_name
    """
    meta: dict = {}
    if trace_name:
        meta["trace_name"] = trace_name
    if trace_id:
        meta["trace_id"] = trace_id
    if user_id:
        meta["trace_user_id"] = user_id
    if session_id:
        meta["trace_session_id"] = session_id
    if tags:
        meta["tags"] = tags
    if generation_name:
        meta["generation_name"] = generation_name
    if extra_metadata:
        meta.update(extra_metadata)
    return meta


async def _call_with_fallback(
    messages: list[dict],
    model: str,
    **kwargs: Any,
) -> Any:
    """
    Try each model in the fallback chain in order.
    Rate limits and service errors cause fallthrough to the next model.
    The last available model gets up to 2 tenacity retries with backoff.
    """
    if model == _DEFAULT_MODEL:
        models_to_try = list(_FALLBACK_MODELS)
    else:
        models_to_try = [model] + [m for m in _FALLBACK_MODELS if m != model]

    last_exc: Optional[Exception] = None

    for i, m in enumerate(models_to_try):
        is_last = i == len(models_to_try) - 1
        try:
            response = await litellm.acompletion(model=m, messages=messages, **kwargs)
            response._model_used = m
            if m != models_to_try[0]:
                log.info("llm_fallback_success", model=m, skipped=models_to_try[0])
            return response
        except (litellm.RateLimitError, litellm.ServiceUnavailableError) as exc:
            log.warning("llm_rate_limited", model=m, falling_back=not is_last)
            last_exc = exc
            if is_last:
                @retry(
                    retry=retry_if_exception_type(
                        (litellm.RateLimitError, litellm.ServiceUnavailableError)
                    ),
                    wait=wait_exponential(multiplier=2, min=4, max=60),
                    stop=stop_after_attempt(2),
                    reraise=True,
                )
                async def _retry_last() -> Any:
                    r = await litellm.acompletion(model=m, messages=messages, **kwargs)
                    r._model_used = m
                    return r

                return await _retry_last()
            continue
        except Exception as exc:
            log.warning("llm_model_error", model=m, error=str(exc)[:120])
            last_exc = exc
            continue

    raise last_exc or RuntimeError("All LLM models failed")


def _parse_response(response: Any, start_time: float, trace_id: Optional[str]) -> LLMResponse:
    latency_ms = round((time.perf_counter() - start_time) * 1000)
    usage = getattr(response, "usage", None)
    text = response.choices[0].message.content or ""
    model_used = getattr(response, "_model_used", response.model)
    cost = 0.0
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        pass

    return LLMResponse(
        text=text,
        model_used=model_used,
        input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
        output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
        total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
        cost_usd=cost,
        latency_ms=latency_ms,
        trace_id=trace_id,
    )


async def llm_chat(
    messages: list[dict],
    model: Optional[str] = None,
    role: Optional[str] = None,
    # ── LangFuse trace context ─────────────────────────────────────────────
    trace_name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    generation_name: Optional[str] = None,
    # ── Pass-through for any other litellm kwargs ──────────────────────────
    **kwargs: Any,
) -> LLMResponse:
    """
    Send a chat completion with full LangFuse tracing context.

    Args:
        messages:        OpenAI-format message list
        model:           Override the model (defaults to role-based selection)
        role:            "extraction" | "response_gen" | None (default routing)
        trace_name:      Human-readable name shown in LangFuse UI
        user_id:         Lead phone or identifier — groups traces by user
        session_id:      Conversation session ID — groups turns into a session
        tags:            Filter tags in LangFuse (e.g. ["whatsapp", "extraction"])
        generation_name: Name for the generation span within the trace
    """
    chosen = model or _pick_model(role)
    # Generate a stable trace_id so we can link to LangFuse after the call
    trace_id = str(uuid.uuid4())

    langfuse_meta = _build_langfuse_metadata(
        trace_name=trace_name or "llm_chat",
        trace_id=trace_id,
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        generation_name=generation_name or trace_name,
        extra_metadata=None,
    )
    if langfuse_meta:
        kwargs["metadata"] = {**kwargs.get("metadata", {}), **langfuse_meta}

    start = time.perf_counter()
    try:
        response = await _call_with_fallback(messages, chosen, **kwargs)
        return _parse_response(response, start, trace_id)
    except Exception as exc:
        log.error("llm_chat_failed", model=chosen, error=str(exc))
        raise


async def llm_complete(
    prompt: str,
    model: Optional[str] = None,
    role: Optional[str] = None,
    trace_name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **kwargs: Any,
) -> LLMResponse:
    """Single-turn completion from a plain string prompt."""
    return await llm_chat(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        role=role,
        trace_name=trace_name or "llm_complete",
        user_id=user_id,
        session_id=session_id,
        tags=tags,
        generation_name=trace_name,
        **kwargs,
    )


async def llm_extract_json(
    prompt: str,
    schema: dict,
    model: Optional[str] = None,
    trace_name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Ask the LLM to return valid JSON matching schema.
    Strips markdown code fences. Raises ValueError on parse failure.
    """
    import json
    import re

    json_prompt = (
        f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n"
        f"{schema}\n\nDo not include any text outside the JSON object."
    )
    response = await llm_complete(
        json_prompt,
        model=model,
        role="extraction",
        trace_name=trace_name or "llm_extract_json",
        user_id=user_id,
        session_id=session_id,
        tags=["extraction"],
    )

    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("llm_json_parse_failed", raw=text[:200], error=str(exc))
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc


async def check_llm_health() -> dict:
    """Health check using the fallback chain — Groq answers when Gemini is rate-limited."""
    if not settings.llm_configured:
        return {"status": "unconfigured", "error": "No LLM API keys set"}

    start = time.perf_counter()
    try:
        result = await llm_complete(
            "Reply with the single word: OK",
            trace_name="health_check",
            tags=["health"],
        )
        return {
            "status": "healthy",
            "latency_ms": result.latency_ms,
            "model": result.model_used,
            "response_preview": result.text[:50],
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000)
        log.error("llm_health_check_failed", error=str(exc))
        return {"status": "unhealthy", "latency_ms": latency_ms, "error": str(exc)[:200]}
