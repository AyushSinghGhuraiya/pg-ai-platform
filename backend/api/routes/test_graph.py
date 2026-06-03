"""
Developer test endpoints for the LangGraph conversation graph.
All routes disabled in production.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/test/graph", tags=["test-graph"])


# ── Request / response models ─────────────────────────────────────────────────

class RunRequest(BaseModel):
    lead_id: str
    message: str
    channel: str = "whatsapp"
    tenant_id: Optional[str] = None


class RunResponse(BaseModel):
    session_id: Optional[str]
    lead_id: Optional[str]
    response: Optional[str]
    last_node: Optional[str]
    state_summary: dict
    decision_log: list


# ── Helpers ───────────────────────────────────────────────────────────────────

def _state_summary(result: dict) -> dict:
    return {
        "session_id": result.get("session_id"),
        "turn_count": result.get("turn_count"),
        "current_phase": result.get("current_phase"),
        "slots_filled": {
            k: v.get("value")
            for k, v in result.get("slots", {}).items()
            if v.get("value")
        },
        "retry_counts": result.get("retry_counts"),
        "needs_human": result.get("needs_human"),
        "should_end_session": result.get("should_end_session"),
        "intent": result.get("intent"),
        "sentiment": result.get("sentiment"),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunResponse)
async def run_graph(req: RunRequest) -> RunResponse:
    """Invoke the graph with a single user message and return the AI reply."""
    from agent.graph import get_graph
    from agent.state import create_initial_state

    tenant_id = req.tenant_id or settings.default_tenant_id
    if not tenant_id:
        raise HTTPException(400, "tenant_id required (or set DEFAULT_TENANT_ID in .env)")

    graph = get_graph()
    config = {"configurable": {"thread_id": req.lead_id}}

    # Build initial state for this turn
    state = create_initial_state(
        lead_id=req.lead_id,
        tenant_id=tenant_id,
        channel=req.channel,
    )
    state["current_user_message"] = req.message
    state["messages"] = [{
        "role": "user",
        "content": req.message,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {},
    }]
    state["last_user_message_at"] = datetime.utcnow().isoformat()

    try:
        result = await graph.ainvoke(state, config)
    except Exception as exc:
        log.exception("graph_run_failed lead=%s", req.lead_id)
        raise HTTPException(500, f"Graph error: {exc}") from exc

    return RunResponse(
        session_id=result.get("session_id"),
        lead_id=result.get("lead_id"),
        response=result.get("last_response"),
        last_node=result.get("last_node"),
        state_summary=_state_summary(result),
        decision_log=result.get("decision_log", [])[-5:],
    )


@router.get("/state/{lead_id}")
async def get_state(lead_id: str) -> dict:
    """Return the persisted state for a lead's conversation thread."""
    from agent.graph import get_graph

    graph = get_graph()
    config = {"configurable": {"thread_id": lead_id}}

    try:
        snapshot = await graph.aget_state(config)
    except Exception as exc:
        log.exception("get_state_failed lead=%s", lead_id)
        raise HTTPException(500, f"Error: {exc}") from exc

    if not snapshot or not snapshot.values:
        return {"error": "No state found", "lead_id": lead_id}

    s = snapshot.values
    return {
        "lead_id": lead_id,
        "session_id": s.get("session_id"),
        "turn_count": s.get("turn_count"),
        "current_phase": s.get("current_phase"),
        "slots": s.get("slots"),
        "retry_counts": s.get("retry_counts"),
        "messages_count": len(s.get("messages", [])),
        "last_node": s.get("last_node"),
        "last_response": s.get("last_response"),
        "needs_human": s.get("needs_human"),
        "decision_log_count": len(s.get("decision_log", [])),
    }


@router.get("/visualize")
async def visualize() -> dict:
    """Return a human-readable description of the graph topology."""
    return {
        "entry_pipeline": "START → load_context → preprocess → extract_slots → validate_slots",
        "router": "validate_slots → strict_router (pure Python, no LLM) → response_node",
        "exit": "any response node → postprocess → END",
        "nodes": {
            "pipeline": ["load_context", "preprocess", "extract_slots", "validate_slots"],
            "sector": [
                "ask_sector_open", "ask_sector_helpful", "ask_sector_examples",
                "ask_sector_options", "verify_sector", "resolve_landmark", "confirm_landmark_choice",
            ],
            "slots": ["ask_pg_type", "ask_budget", "ask_visit_date", "confirm_visit"],
            "action": ["search_properties", "share_properties"],
            "exit": ["human_handoff", "graceful_end"],
            "output": ["response_generator", "postprocess"],
        },
        "router_priority": [
            "1. needs_human / should_end / asks_human",
            "2. turn_count > 30 / consecutive_failures >= 3 / angry",
            "3. landmark resolution",
            "4. sector gate (4 progressive attempts → handoff)",
            "5. pg_type gate (3 attempts → handoff)",
            "6. budget gate (3 attempts → handoff)",
            "7. search → share_properties",
            "8. visit_date gate (3 attempts → graceful_end)",
            "9. confirm_visit",
            "10. graceful_end",
        ],
    }


@router.delete("/state/{lead_id}")
async def reset_state(lead_id: str) -> dict:
    """Delete all checkpoints for a lead (reset their conversation)."""
    if settings.is_production:
        raise HTTPException(403, "Not available in production")

    from db.client import get_supabase
    client = get_supabase()

    cp_result = await (
        client.table("conversation_checkpoints")
        .delete()
        .eq("thread_id", lead_id)
        .execute()
    )
    wr_result = await (
        client.table("conversation_checkpoint_writes")
        .delete()
        .eq("thread_id", lead_id)
        .execute()
    )

    return {
        "lead_id": lead_id,
        "checkpoints_deleted": len(cp_result.data or []),
        "writes_deleted": len(wr_result.data or []),
        "message": "State reset — next call will start a fresh conversation",
    }
