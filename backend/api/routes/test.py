"""
Developer test endpoints — remove or auth-protect before production.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from services.langfuse_client import get_trace_url, is_active, propagate_trace_context
from services.llm_client import llm_complete

router = APIRouter(prefix="/test", tags=["dev-test"])


class LLMTestRequest(BaseModel):
    prompt: str
    model: Optional[str] = None
    # Optional trace context — pass these to see grouped traces in LangFuse
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class LLMTestResponse(BaseModel):
    model: str
    response: str
    tokens: dict
    cost_usd: float
    latency_ms: int
    trace_id: Optional[str] = None
    trace_url: Optional[str] = None   # click to open in LangFuse dashboard


@router.post("/llm", response_model=LLMTestResponse)
async def test_llm(body: LLMTestRequest) -> LLMTestResponse:
    """
    Send a prompt to the LLM and return full metadata.
    Pass user_id / session_id to see them in the LangFuse Traces UI.
    """
    with propagate_trace_context(
        trace_name="test_llm",
        user_id=body.user_id,
        session_id=body.session_id,
        tags=["dev", "test"],
    ):
        result = await llm_complete(
            body.prompt,
            model=body.model,
            trace_name="test_llm",
            user_id=body.user_id,
            session_id=body.session_id,
            tags=["dev", "test"],
        )

    trace_url = get_trace_url(result.trace_id) if result.trace_id and is_active() else None

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
        trace_id=result.trace_id,
        trace_url=trace_url,
    )
