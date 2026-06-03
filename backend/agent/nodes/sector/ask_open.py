"""ask_sector_open — first attempt, open question about sector."""

from __future__ import annotations

import logging

from agent.state import ConversationState, increment_retry, log_decision

log = logging.getLogger(__name__)


async def ask_sector_open_node(state: ConversationState) -> dict:
    log.info("[ask_sector_open] called")
    return {
        "last_response": "Sir, kis sector me PG dhundh rahe ho?",
        "ai_response_pending": True,
        "last_node": "ask_sector_open",
        **increment_retry(state, "sector"),
        **log_decision(state, "ask_sector_open", "asked_sector_open"),
    }
