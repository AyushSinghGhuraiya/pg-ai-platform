"""
preprocess — detect intent, sentiment, language from the user message.
STUB: returns safe defaults. Real NLU logic comes in Day 10.
"""

from __future__ import annotations

import logging

from agent.state import ConversationState, log_decision

log = logging.getLogger(__name__)


async def preprocess_node(state: ConversationState) -> dict:
    log.info("[preprocess] called session=%s", state["session_id"])
    return {
        "intent": "qualifying",
        "sentiment": "neutral",
        "language": "hinglish",
        "last_node": "preprocess",
        **log_decision(state, "preprocess", "stub_executed"),
    }
