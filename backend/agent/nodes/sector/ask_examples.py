"""ask_sector_examples — third attempt, give landmark examples."""

from __future__ import annotations
import logging
from agent.state import ConversationState, increment_retry, log_decision
log = logging.getLogger(__name__)

async def ask_sector_examples_node(state: ConversationState) -> dict:
    log.info("[ask_sector_examples] called")
    return {
        "last_response": "Sir, jaise Huda City, Cyber Hub, MG Road?",
        "ai_response_pending": True,
        "last_node": "ask_sector_examples",
        **increment_retry(state, "sector"),
        **log_decision(state, "ask_sector_examples", "asked_sector_examples"),
    }
