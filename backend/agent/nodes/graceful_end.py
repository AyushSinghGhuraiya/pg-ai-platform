"""graceful_end — close the conversation cleanly after success or giving up."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def graceful_end_node(state: ConversationState) -> dict:
    log.info("[graceful_end] called phase=%s", state.get("current_phase"))
    outcome = "qualified" if state.get("current_phase") == "confirmed" else "abandoned"
    return {
        "last_response": "Dhanyavaad sir! Aapse phir baat hogi.",
        "ai_response_pending": True,
        "should_end_session": True,
        "session_outcome": outcome,
        "last_node": "graceful_end",
        **log_decision(state, "graceful_end", "session_ended"),
    }
