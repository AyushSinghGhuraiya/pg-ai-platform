"""
extract_slots — extract qualification slots from the user message.
STUB: returns empty extraction. Real logic comes in Day 10-11.
"""

from __future__ import annotations

import logging

from agent.state import ConversationState, log_decision

log = logging.getLogger(__name__)


async def extract_slots_node(state: ConversationState) -> dict:
    log.info("[extract_slots] called session=%s", state["session_id"])
    return {
        "extracted_this_turn": {},
        "last_node": "extract_slots",
        **log_decision(state, "extract_slots", "stub_executed"),
    }
