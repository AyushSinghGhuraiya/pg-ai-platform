"""search_properties — query DB for matching properties given filled slots."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def search_properties_node(state: ConversationState) -> dict:
    log.info("[search_properties] called")
    return {
        "search_attempted": True,
        "matched_properties": [],
        "current_phase": "matching",
        "last_node": "search_properties",
        **log_decision(state, "search_properties", "stub_executed"),
    }
