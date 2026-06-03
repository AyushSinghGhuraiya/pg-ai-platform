"""resolve_landmark — look up a landmark in location_aliases and map to sector(s)."""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def resolve_landmark_node(state: ConversationState) -> dict:
    log.info("[resolve_landmark] called landmark=%s", state.get("pending_landmark"))
    return {
        "last_node": "resolve_landmark",
        **log_decision(state, "resolve_landmark", "stub_executed"),
    }
