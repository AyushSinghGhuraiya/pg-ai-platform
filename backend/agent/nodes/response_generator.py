"""
response_generator — final response polish / fallback.
STUB: most nodes set last_response directly; this is a no-op pass-through for now.
"""

from __future__ import annotations
import logging
from agent.state import ConversationState, log_decision
log = logging.getLogger(__name__)

async def response_generator_node(state: ConversationState) -> dict:
    log.info("[response_generator] called")
    return {
        "ai_response_pending": False,
        "last_node": "response_generator",
        **log_decision(state, "response_generator", "stub_executed"),
    }
