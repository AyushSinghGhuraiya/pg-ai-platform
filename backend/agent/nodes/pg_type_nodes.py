"""ask_pg_type — ask whether the lead wants boys/girls/coliving PG."""

from __future__ import annotations
import logging
from agent.state import ConversationState, increment_retry, log_decision
log = logging.getLogger(__name__)

async def ask_pg_type_node(state: ConversationState) -> dict:
    log.info("[ask_pg_type] called")
    return {
        "last_response": "Sir, Boys PG, Girls PG, ya Coliving?",
        "ai_response_pending": True,
        "last_node": "ask_pg_type",
        **increment_retry(state, "pg_type"),
        **log_decision(state, "ask_pg_type", "asking_pg_type"),
    }
