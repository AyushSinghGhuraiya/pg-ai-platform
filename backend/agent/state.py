"""
ConversationState — the data structure that flows through the LangGraph.

All nodes read from and write updates to this state.
thread_id = lead_id (one thread per lead conversation).
"""

from __future__ import annotations

import operator
import uuid
from datetime import datetime
from typing import Annotated, Literal, Optional, TypedDict


# ═══════════════════════════════════════════════════════════
# SUB-TYPES
# ═══════════════════════════════════════════════════════════


class Slot(TypedDict, total=False):
    """A single qualification slot (e.g., sector, budget)."""
    value: Optional[str]
    confidence: float
    method: str            # explicit | inferred | landmark | confirmed
    filled_at: Optional[str]
    source_message: Optional[str]
    history: list[dict]


class Message(TypedDict):
    """One turn in the conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: str
    metadata: dict


class DecisionLogEntry(TypedDict):
    """One routing/decision event for audit trail."""
    node: str
    decision: str
    reason: str
    state_before: dict
    timestamp: str


class LeadProfile(TypedDict, total=False):
    """Lead's accumulated profile loaded from DB."""
    preferred_sectors: list[str]
    preferred_pg_types: list[str]
    budget_max: Optional[int]
    engagement_level: str        # new | cold | warm | hot | dead
    conversation_summary: Optional[str]
    last_blocker: Optional[str]
    total_conversations: int
    total_calls: int
    total_whatsapp_msgs: int
    visits_scheduled: int
    visits_completed: int
    last_interaction_at: Optional[str]


class PropertyMatch(TypedDict):
    """A matched property with relevance score."""
    property_id: str
    name: str
    sector: str
    pg_type: str
    rent_min: int
    rent_max: int
    available_beds: int
    amenities: list[str]
    score: float
    photos: list[str]


# ═══════════════════════════════════════════════════════════
# MAIN STATE
# ═══════════════════════════════════════════════════════════


class ConversationState(TypedDict):
    """
    Complete state for one conversation session.

    The `messages` field uses operator.add as its reducer so every node that
    returns {"messages": [...]} *appends* to the list rather than replacing it.
    All other fields are replaced on each update.
    """

    # ── Identity ─────────────────────────────────────────
    session_id: str
    lead_id: str
    tenant_id: str
    channel: Literal["whatsapp", "call", "instagram"]

    # ── Conversation history ──────────────────────────────
    messages: Annotated[list[Message], operator.add]
    turn_count: int
    started_at: str
    last_user_message_at: Optional[str]

    # ── Current turn ──────────────────────────────────────
    current_user_message: Optional[str]
    intent: Optional[str]        # qualifying | asks_human | consent_withdrawal | off_topic | greeting | goodbye
    sentiment: Optional[str]     # positive | neutral | frustrated | angry
    language: Optional[str]      # hinglish | hindi | english | mixed
    extracted_this_turn: dict    # Raw extraction output from current message

    # ── Slots (core qualification data) ──────────────────
    # Keys: sector, pg_type, budget, visit_date, landmark, name, move_in_date
    slots: dict[str, Slot]
    retry_counts: dict[str, int]  # Per-slot retry counter

    # ── Lead profile (loaded from DB) ────────────────────
    lead_profile: LeadProfile
    profile_loaded: bool

    # ── Property matching ─────────────────────────────────
    matched_properties: list[PropertyMatch]
    properties_shown: bool
    selected_property_id: Optional[str]
    search_attempted: bool

    # ── Landmark resolution ───────────────────────────────
    pending_landmark: Optional[str]
    landmark_candidates: list[str]
    landmark_confirmed: bool

    # ── Phase tracking ────────────────────────────────────
    current_phase: Literal["init", "qualifying", "matching", "booking", "confirmed", "done"]
    completed_phases: list[str]

    # ── Escalation ────────────────────────────────────────
    needs_human: bool
    escalation_reason: Optional[str]
    # Values: sector_failed | user_asked | angry_user | low_confidence | tool_failure | conversation_too_long
    consecutive_failures: int

    # ── Routing ───────────────────────────────────────────
    next_node: Optional[str]
    last_node: Optional[str]

    # ── Session control ───────────────────────────────────
    should_end_session: bool
    session_outcome: Optional[str]
    # Values: qualified | booked | escalated | abandoned | dnd | invalid

    # ── Response generation ───────────────────────────────
    ai_response_pending: bool
    last_response: Optional[str]
    response_attempts: int

    # ── Debugging / audit ─────────────────────────────────
    decision_log: list[DecisionLogEntry]
    errors: list[dict]

    # ── Catch-all metadata ────────────────────────────────
    metadata: dict


# ═══════════════════════════════════════════════════════════
# FACTORY
# ═══════════════════════════════════════════════════════════


def create_initial_state(
    lead_id: str,
    tenant_id: str,
    channel: str = "whatsapp",
    session_id: Optional[str] = None,
) -> ConversationState:
    """Create fresh state for a new conversation."""
    return ConversationState(
        # Identity
        session_id=session_id or str(uuid.uuid4()),
        lead_id=lead_id,
        tenant_id=tenant_id,
        channel=channel,  # type: ignore[arg-type]
        # Conversation
        messages=[],
        turn_count=0,
        started_at=datetime.utcnow().isoformat(),
        last_user_message_at=None,
        # Current turn
        current_user_message=None,
        intent=None,
        sentiment=None,
        language=None,
        extracted_this_turn={},
        # Slots — all empty
        slots={
            "sector":      {"value": None, "confidence": 0.0, "method": None, "history": []},
            "pg_type":     {"value": None, "confidence": 0.0, "method": None, "history": []},
            "budget":      {"value": None, "confidence": 0.0, "method": None, "history": []},
            "visit_date":  {"value": None, "confidence": 0.0, "method": None, "history": []},
            "landmark":    {"value": None, "confidence": 0.0, "method": None, "history": []},
            "name":        {"value": None, "confidence": 0.0, "method": None, "history": []},
            "move_in_date":{"value": None, "confidence": 0.0, "method": None, "history": []},
        },
        retry_counts={"sector": 0, "pg_type": 0, "budget": 0, "visit_date": 0},
        # Profile
        lead_profile={},
        profile_loaded=False,
        # Properties
        matched_properties=[],
        properties_shown=False,
        selected_property_id=None,
        search_attempted=False,
        # Landmark
        pending_landmark=None,
        landmark_candidates=[],
        landmark_confirmed=False,
        # Phase
        current_phase="init",
        completed_phases=[],
        # Escalation
        needs_human=False,
        escalation_reason=None,
        consecutive_failures=0,
        # Routing
        next_node=None,
        last_node=None,
        # Session control
        should_end_session=False,
        session_outcome=None,
        # Response
        ai_response_pending=False,
        last_response=None,
        response_attempts=0,
        # Debug
        decision_log=[],
        errors=[],
        # Metadata
        metadata={},
    )


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════


def get_slot_value(state: ConversationState, slot_name: str) -> Optional[str]:
    """Return the raw value of a slot, or None."""
    return state.get("slots", {}).get(slot_name, {}).get("value")


def is_slot_filled(state: ConversationState, slot_name: str) -> bool:
    """True if slot has a value with confidence >= 0.7."""
    slot = state.get("slots", {}).get(slot_name, {})
    return slot.get("value") is not None and slot.get("confidence", 0.0) >= 0.7


def get_retry_count(state: ConversationState, slot_name: str) -> int:
    """How many times we've already asked for this slot."""
    return state.get("retry_counts", {}).get(slot_name, 0)


def increment_retry(state: ConversationState, slot_name: str) -> dict:
    """Return a state-update dict that bumps the retry counter for one slot."""
    counts = dict(state.get("retry_counts", {}))
    counts[slot_name] = counts.get(slot_name, 0) + 1
    return {"retry_counts": counts}


def log_decision(
    state: ConversationState,
    node: str,
    decision: str,
    reason: str = "",
    state_snapshot: Optional[dict] = None,
) -> dict:
    """Return a state-update dict that appends one entry to decision_log."""
    entry: DecisionLogEntry = {
        "node": node,
        "decision": decision,
        "reason": reason,
        "state_before": state_snapshot or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {"decision_log": list(state.get("decision_log", [])) + [entry]}
