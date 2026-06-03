"""confirm_landmark_choice — landmark maps to multiple sectors, ask user to pick."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def confirm_landmark_choice_node(state: ConversationState) -> dict:
    log.info("[confirm_landmark_choice] called candidates=%s", state.get("landmark_candidates"))
    return {
        "last_response": "Sir, woh landmark Sector 44 aur 45 dono ke paas hai. Kaunsa prefer karoge?",
        "ai_response_pending": True,
        "last_node": "confirm_landmark_choice",
        **log_decision(state, "confirm_landmark_choice", "asking_choice"),
    }
