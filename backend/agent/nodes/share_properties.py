"""share_properties — send matched property cards to the lead via WhatsApp."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def share_properties_node(state: ConversationState) -> dict:
    log.info("[share_properties] called count=%d", len(state.get("matched_properties", [])))
    return {
        "last_response": "Sir, 3 options bhej raha hu...",
        "ai_response_pending": True,
        "properties_shown": True,
        "last_node": "share_properties",
        **log_decision(state, "share_properties", "sharing_properties"),
    }
