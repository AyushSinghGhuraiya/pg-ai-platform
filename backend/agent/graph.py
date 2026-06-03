"""
Build and compile the LangGraph conversation graph.

Flow per turn:
  START
  → load_context → preprocess → extract_slots → validate_slots
  → strict_router (conditional edge)
  → one response-generating node
  → postprocess
  → END

State persistence: SupabaseCheckpointSaver (thread_id = lead_id).
For local / test runs without a DB, pass checkpointer=MemorySaver().
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from agent.checkpointer import get_checkpointer
from agent.nodes import (
    ask_budget_node,
    ask_pg_type_node,
    ask_sector_examples_node,
    ask_sector_helpful_node,
    ask_sector_open_node,
    ask_sector_options_node,
    ask_visit_date_node,
    confirm_landmark_choice_node,
    confirm_visit_node,
    extract_slots_node,
    graceful_end_node,
    human_handoff_node,
    load_context_node,
    postprocess_node,
    preprocess_node,
    resolve_landmark_node,
    response_generator_node,
    search_properties_node,
    share_properties_node,
    validate_slots_node,
    verify_sector_node,
)
from agent.router import strict_router
from agent.state import ConversationState

log = logging.getLogger(__name__)

# All nodes that generate a response (they all funnel into postprocess)
_RESPONSE_NODES = [
    "ask_sector_open",
    "ask_sector_helpful",
    "ask_sector_examples",
    "ask_sector_options",
    "verify_sector",
    "resolve_landmark",
    "confirm_landmark_choice",
    "ask_pg_type",
    "ask_budget",
    "ask_visit_date",
    "search_properties",
    "share_properties",
    "confirm_visit",
    "human_handoff",
    "graceful_end",
]


def build_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
) -> StateGraph:
    """
    Construct and compile the conversation StateGraph.

    Args:
        checkpointer: Override the default Supabase checkpointer (useful in
                      tests — pass MemorySaver() to avoid hitting the DB).
    """
    workflow = StateGraph(ConversationState)

    # ── Register nodes ────────────────────────────────────────────────────────
    workflow.add_node("load_context", load_context_node)
    workflow.add_node("preprocess", preprocess_node)
    workflow.add_node("extract_slots", extract_slots_node)
    workflow.add_node("validate_slots", validate_slots_node)

    workflow.add_node("ask_sector_open", ask_sector_open_node)
    workflow.add_node("ask_sector_helpful", ask_sector_helpful_node)
    workflow.add_node("ask_sector_examples", ask_sector_examples_node)
    workflow.add_node("ask_sector_options", ask_sector_options_node)
    workflow.add_node("verify_sector", verify_sector_node)
    workflow.add_node("resolve_landmark", resolve_landmark_node)
    workflow.add_node("confirm_landmark_choice", confirm_landmark_choice_node)

    workflow.add_node("ask_pg_type", ask_pg_type_node)
    workflow.add_node("ask_budget", ask_budget_node)
    workflow.add_node("ask_visit_date", ask_visit_date_node)
    workflow.add_node("confirm_visit", confirm_visit_node)

    workflow.add_node("search_properties", search_properties_node)
    workflow.add_node("share_properties", share_properties_node)

    workflow.add_node("human_handoff", human_handoff_node)
    workflow.add_node("graceful_end", graceful_end_node)

    workflow.add_node("response_generator", response_generator_node)
    workflow.add_node("postprocess", postprocess_node)

    # ── Linear entry pipeline ─────────────────────────────────────────────────
    workflow.add_edge(START, "load_context")
    workflow.add_edge("load_context", "preprocess")
    workflow.add_edge("preprocess", "extract_slots")
    workflow.add_edge("extract_slots", "validate_slots")

    # ── Conditional routing after validate_slots ──────────────────────────────
    workflow.add_conditional_edges(
        "validate_slots",
        strict_router,
        {node: node for node in _RESPONSE_NODES},
    )

    # ── All response nodes funnel into postprocess → END ──────────────────────
    for node in _RESPONSE_NODES:
        workflow.add_edge(node, "postprocess")
    workflow.add_edge("postprocess", END)

    # ── Compile ───────────────────────────────────────────────────────────────
    cp = checkpointer if checkpointer is not None else get_checkpointer()
    compiled = workflow.compile(checkpointer=cp)
    log.info("graph compiled successfully")
    return compiled


# ── Singleton ─────────────────────────────────────────────────────────────────

_graph = None


def get_graph():
    """Return the singleton compiled graph (Supabase-backed checkpointer)."""
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
