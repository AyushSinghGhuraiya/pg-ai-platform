"""
LiteLLM unified gateway for all LLM providers.

Routing:
  default        → gemini/gemini-1.5-flash (free)
  extraction     → gemini/gemini-1.5-flash (or gpt-4o-mini when key available)
  response_gen   → gemini/gemini-1.5-flash (or claude-3-5-haiku when key available)
  fallback chain → gemini → groq/llama-3.3-70b-versatile → error

Each call:
  - Logs to LangFuse automatically (via litellm callback)
  - Retries up to 3x with exponential backoff on transient errors
  - Returns structured LLMResponse with tokens, cost, latency
"""

from __future__ import annotations

import os
import time
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

# Fallback chain (first that works wins)
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
    langfuse_trace_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)


def init_llm() -> None:
    """Configure LiteLLM env vars so providers work. Call at startup."""
    if settings.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = settings.gemini_api_key
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.anthropic_api_key:
        os.environ["ANTHROPIC_API_KEY"] = settings.anthropic_api_key

    # Quiet LiteLLM's verbose output unless in debug mode
    litellm.set_verbose = settings.is_development

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


async def _call_with_fallback(
    messages: list[dict],
    model: str,
    **kwargs: Any,
) -> Any:
    """
    Call litellm with automatic fallback chain.
    If the primary model rate-limits or is unavailable, tries the next model.
    Retries the last model up to 3x with backoff on transient errors.
    """
    # Build the list of models to attempt in order
    if model == _DEFAULT_MODEL:
        models_to_try = list(_FALLBACK_MODELS)
    else:
        # Custom model first, then fallbacks
        models_to_try = [model] + [m for m in _FALLBACK_MODELS if m != model]

    last_exc: Optional[Exception] = None

    for i, m in enumerate(models_to_try):
        is_last = i == len(models_to_try) - 1
        try:
            response = await litellm.acompletion(model=m, messages=messages, **kwargs)
            response._model_used = m
            if m != models_to_try[0]:
                log.info("llm_fallback_success", model=m, original=models_to_try[0])
            return response
        except (litellm.RateLimitError, litellm.ServiceUnavailableError) as exc:
            log.warning("llm_rate_limited", model=m, fallback_available=not is_last)
            last_exc = exc
            if is_last:
                # Retry the last available model with backoff
                @retry(
                    retry=retry_if_exception_type((litellm.RateLimitError, litellm.ServiceUnavailableError)),
                    wait=wait_exponential(multiplier=2, min=4, max=60),
                    stop=stop_after_attempt(2),
                    reraise=True,
                )
                async def _retry_last() -> Any:
                    r = await litellm.acompletion(model=m, messages=messages, **kwargs)
                    r._model_used = m
                    return r
                return await _retry_last()
            continue  # try next model
        except Exception as exc:
            log.warning("llm_model_error", model=m, error=str(exc)[:100])
            last_exc = exc
            continue

    raise last_exc or RuntimeError("All LLM models failed")


def _parse_response(response: Any, start_time: float) -> LLMResponse:
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
    )


async def llm_chat(
    messages: list[dict],
    model: Optional[str] = None,
    role: Optional[str] = None,
    **kwargs: Any,
) -> LLMResponse:
    """Send a chat completion. messages = [{"role": ..., "content": ...}]."""
    chosen = model or _pick_model(role)
    start = time.perf_counter()
    try:
        response = await _call_with_fallback(messages, chosen, **kwargs)
        return _parse_response(response, start)
    except Exception as exc:
        log.error("llm_chat_failed", model=chosen, error=str(exc))
        raise


async def llm_complete(
    prompt: str,
    model: Optional[str] = None,
    role: Optional[str] = None,
    **kwargs: Any,
) -> LLMResponse:
    """Single-turn completion from a plain prompt string."""
    return await llm_chat(
        messages=[{"role": "user", "content": prompt}],
        model=model,
        role=role,
        **kwargs,
    )


async def llm_extract_json(
    prompt: str,
    schema: dict,
    model: Optional[str] = None,
) -> dict:
    """
    Ask the LLM to return valid JSON matching schema.
    Returns parsed dict. Raises ValueError if JSON is invalid.
    """
    json_prompt = (
        f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n"
        f"{schema}\n\nDo not include any text outside the JSON object."
    )
    response = await llm_complete(json_prompt, model=model, role="extraction")

    import json
    import re

    text = response.text.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("llm_json_parse_failed", raw=text[:200], error=str(exc))
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc


async def check_llm_health() -> dict:
    """Health check — uses fallback chain so rate limits don't report unhealthy."""
    if not settings.llm_configured:
        return {"status": "unconfigured", "error": "No LLM API keys set"}

    start = time.perf_counter()
    try:
        # Use fallback chain: if Gemini is rate-limited, Groq will answer
        result = await llm_complete("Reply with the single word: OK")
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
