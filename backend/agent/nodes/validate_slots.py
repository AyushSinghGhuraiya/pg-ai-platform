"""
validate_slots — sanity-check extracted slot values before routing.
STUB: pass-through. Real validation comes in Day 10.
"""

from __future__ import annotations

import logging

from agent.state import ConversationState, log_decision

log = logging.getLogger(__name__)


async def validate_slots_node(state: ConversationState) -> dict:
    log.info("[validate_slots] called")
    return {
        "last_node": "validate_slots",
        **log_decision(state, "validate_slots", "stub_executed"),
    }
