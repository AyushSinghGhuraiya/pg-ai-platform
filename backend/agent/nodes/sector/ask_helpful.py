"""ask_sector_helpful — second attempt, hint about landmarks."""

from __future__ import annotations

import logging

from agent.state import ConversationState, increment_retry, log_decision

log = logging.getLogger(__name__)


async def ask_sector_helpful_node(state: ConversationState) -> dict:
    log.info("[ask_sector_helpful] called")
    return {
        "last_response": "Sir, koi area ya landmark ke paas?",
        "ai_response_pending": True,
        "last_node": "ask_sector_helpful",
        **increment_retry(state, "sector"),
        **log_decision(state, "ask_sector_helpful", "asked_sector_helpful"),
    }
