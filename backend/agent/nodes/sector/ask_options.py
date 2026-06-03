"""ask_sector_options — fourth attempt, offer direct sector choices."""

from __future__ import annotations
import logging
from agent.state import ConversationState, increment_retry, log_decision
log = logging.getLogger(__name__)

async def ask_sector_options_node(state: ConversationState) -> dict:
    log.info("[ask_sector_options] called")
    return {
        "last_response": "Sir, Sector 44, 45, ya 46 mein chahiye?",
        "ai_response_pending": True,
        "last_node": "ask_sector_options",
        **increment_retry(state, "sector"),
        **log_decision(state, "ask_sector_options", "asked_sector_options"),
    }
