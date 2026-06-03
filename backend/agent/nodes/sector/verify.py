"""verify_sector — low-confidence sector, ask for confirmation."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def verify_sector_node(state: ConversationState) -> dict:
    log.info("[verify_sector] called")
    return {
        "last_response": "Sir, confirm karu - aapne kaunsa sector kaha?",
        "ai_response_pending": True,
        "last_node": "verify_sector",
        **log_decision(state, "verify_sector", "verifying_sector"),
    }
