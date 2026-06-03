"""human_handoff — escalate the conversation to a human sales agent."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def human_handoff_node(state: ConversationState) -> dict:
    reason = state.get("escalation_reason", "unknown")
    log.info("[human_handoff] called reason=%s", reason)
    return {
        "last_response": "Sir, humari team 10 min mein aapko contact karegi.",
        "ai_response_pending": True,
        "needs_human": True,
        "should_end_session": True,
        "session_outcome": "escalated",
        "last_node": "human_handoff",
        **log_decision(state, "human_handoff", "escalated", reason),
    }
