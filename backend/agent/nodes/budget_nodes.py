"""ask_budget — ask for the lead's monthly budget."""

from __future__ import annotations
import logging
from agent.state import ConversationState, increment_retry, log_decision
log = logging.getLogger(__name__)

async def ask_budget_node(state: ConversationState) -> dict:
    log.info("[ask_budget] called")
    return {
        "last_response": "Sir, monthly budget kitna hai? (e.g., 10K, 15K)",
        "ai_response_pending": True,
        "last_node": "ask_budget",
        **increment_retry(state, "budget"),
        **log_decision(state, "ask_budget", "asking_budget"),
    }
