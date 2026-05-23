"""
Developer test endpoints — remove or auth-protect before production.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.llm_client import llm_complete
from services.langfuse_client import trace

router = APIRouter(prefix="/test", tags=["dev-test"])


class LLMTestRequest(BaseModel):
    prompt: str
    model: Optional[str] = None


class LLMTestResponse(BaseModel):
    model: str
    response: str
    tokens: dict
    cost_usd: float
    latency_ms: int
    langfuse_trace_id: Optional[str] = None


@router.post("/llm", response_model=LLMTestResponse)
async def test_llm(body: LLMTestRequest) -> LLMTestResponse:
    """Send a prompt to the configured LLM and return the full response metadata."""
    t = trace("test_llm", metadata={"prompt": body.prompt[:100]})
    trace_id = getattr(t, "id", None) if t else None

    result = await llm_complete(body.prompt, model=body.model)

    return LLMTestResponse(
        model=result.model_used,
        response=result.text,
        tokens={
            "input": result.input_tokens,
            "output": result.output_tokens,
            "total": result.total_tokens,
        },
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        langfuse_trace_id=trace_id,
    )
