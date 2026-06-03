"""
strict_router — the deterministic routing brain of the agent.

Pure Python decision tree — zero LLM calls.
Called by the conditional edge after validate_slots.
Returns the name of the next node to run.
"""

from __future__ import annotations

import logging
from typing import Literal

from agent.state import ConversationState, get_retry_count, is_slot_filled

log = logging.getLogger(__name__)


def strict_router(state: ConversationState) -> str:
    """Decide which node runs next based solely on current state."""

    # ── Priority 0: Emergency exits ──────────────────────────────────────────

    if state.get("needs_human"):
        log.info("[router] needs_human=True → human_handoff")
        return "human_handoff"

    if state.get("should_end_session"):
        log.info("[router] should_end_session=True → graceful_end")
        return "graceful_end"

    intent = state.get("intent", "")
    if intent == "asks_human":
        log.info("[router] user asked for human → human_handoff")
        return "human_handoff"

    if state.get("turn_count", 0) > 30:
        log.info("[router] turn_count>30 → human_handoff")
        return "human_handoff"

    if state.get("consecutive_failures", 0) >= 3:
        log.info("[router] consecutive_failures>=3 → human_handoff")
        return "human_handoff"

    if state.get("sentiment") == "angry":
        log.info("[router] angry user → human_handoff")
        return "human_handoff"

    # ── Landmark resolution ──────────────────────────────────────────────────

    if state.get("pending_landmark") and not state.get("landmark_confirmed"):
        log.info("[router] pending_landmark → resolve_landmark")
        return "resolve_landmark"

    if len(state.get("landmark_candidates", [])) > 1:
        log.info("[router] multiple landmark candidates → confirm_landmark_choice")
        return "confirm_landmark_choice"

    # ── Sector gate ──────────────────────────────────────────────────────────

    if not is_slot_filled(state, "sector"):
        retry = get_retry_count(state, "sector")
        if retry == 0:
            log.info("[router] sector empty retry=0 → ask_sector_open")
            return "ask_sector_open"
        elif retry == 1:
            log.info("[router] sector empty retry=1 → ask_sector_helpful")
            return "ask_sector_helpful"
        elif retry == 2:
            log.info("[router] sector empty retry=2 → ask_sector_examples")
            return "ask_sector_examples"
        elif retry == 3:
            log.info("[router] sector empty retry=3 → ask_sector_options")
            return "ask_sector_options"
        else:
            log.info("[router] sector failed after retries → human_handoff")
            return "human_handoff"

    sector_slot = state.get("slots", {}).get("sector", {})
    if sector_slot.get("value") and sector_slot.get("confidence", 0.0) < 0.7:
        log.info("[router] sector low confidence → verify_sector")
        return "verify_sector"

    # ── PG-type gate ─────────────────────────────────────────────────────────

    if not is_slot_filled(state, "pg_type"):
        retry = get_retry_count(state, "pg_type")
        if retry < 3:
            log.info("[router] pg_type empty retry=%d → ask_pg_type", retry)
            return "ask_pg_type"
        log.info("[router] pg_type failed → human_handoff")
        return "human_handoff"

    # ── Budget gate ──────────────────────────────────────────────────────────

    if not is_slot_filled(state, "budget"):
        retry = get_retry_count(state, "budget")
        if retry < 3:
            log.info("[router] budget empty retry=%d → ask_budget", retry)
            return "ask_budget"
        log.info("[router] budget failed → human_handoff")
        return "human_handoff"

    # ── Action phase: search → show → book ───────────────────────────────────

    if not state.get("search_attempted"):
        log.info("[router] all slots filled → search_properties")
        return "search_properties"

    if state.get("search_attempted") and not state.get("matched_properties"):
        log.info("[router] no matches found → human_handoff")
        return "human_handoff"

    if state.get("matched_properties") and not state.get("properties_shown"):
        log.info("[router] properties ready → share_properties")
        return "share_properties"

    # ── Visit booking ────────────────────────────────────────────────────────

    if state.get("properties_shown") and not is_slot_filled(state, "visit_date"):
        retry = get_retry_count(state, "visit_date")
        if retry < 3:
            log.info("[router] visit_date empty retry=%d → ask_visit_date", retry)
            return "ask_visit_date"
        log.info("[router] visit_date failed → graceful_end")
        return "graceful_end"

    if is_slot_filled(state, "visit_date") and state.get("current_phase") != "confirmed":
        log.info("[router] visit_date filled → confirm_visit")
        return "confirm_visit"

    # ── Done ─────────────────────────────────────────────────────────────────

    log.info("[router] conversation complete → graceful_end")
    return "graceful_end"


def should_continue(state: ConversationState) -> Literal["continue", "end"]:
    """Used by the edge from postprocess if we ever want a loop-back."""
    if state.get("should_end_session"):
        return "end"
    return "continue"
