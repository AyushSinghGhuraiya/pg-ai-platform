"""
load_context — load lead profile + conversation history from DB.
STUB: logs and returns defaults. Logic comes in Day 14+.
"""

from __future__ import annotations

import logging

from agent.state import ConversationState, log_decision

log = logging.getLogger(__name__)


async def load_context_node(state: ConversationState) -> dict:
    log.info("[load_context] called lead=%s", state["lead_id"])
    return {
        "profile_loaded": True,
        "last_node": "load_context",
        **log_decision(state, "load_context", "stub_executed", "profile loading not yet implemented"),
    }
