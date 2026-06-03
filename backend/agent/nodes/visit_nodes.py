"""visit_nodes — ask for and confirm a property visit date."""

from __future__ import annotations
import logging
from agent.state import ConversationState, increment_retry, log_decision
log = logging.getLogger(__name__)

async def ask_visit_date_node(state: ConversationState) -> dict:
    log.info("[ask_visit_date] called")
    return {
        "last_response": "Sir, visit kab karna chahenge?",
        "ai_response_pending": True,
        "last_node": "ask_visit_date",
        **increment_retry(state, "visit_date"),
        **log_decision(state, "ask_visit_date", "asking_visit_date"),
    }

async def confirm_visit_node(state: ConversationState) -> dict:
    log.info("[confirm_visit] called")
    return {
        "last_response": "Visit confirmed! Address aapko bhej diya hai.",
        "ai_response_pending": True,
        "current_phase": "confirmed",
        "last_node": "confirm_visit",
        **log_decision(state, "confirm_visit", "visit_confirmed"),
    }
