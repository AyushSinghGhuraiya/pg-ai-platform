"""
postprocess — after a response node runs:
  - append the AI message to history
  - increment turn count
  - (Day 14+) save profile updates, trigger follow-up jobs
STUB: appends message + bumps turn_count.
"""

from __future__ import annotations
import logging
from datetime import datetime
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def postprocess_node(state: ConversationState) -> dict:
    log.info("[postprocess] called turn=%d", state.get("turn_count", 0))

    new_messages = []
    if state.get("last_response"):
        new_messages = [{
            "role": "assistant",
            "content": state["last_response"],
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {"node": state.get("last_node")},
        }]

    return {
        "messages": new_messages,        # appended by operator.add reducer
        "turn_count": state.get("turn_count", 0) + 1,
        "ai_response_pending": False,
        "last_node": "postprocess",
        **log_decision(state, "postprocess", "post_processing_complete"),
    }
