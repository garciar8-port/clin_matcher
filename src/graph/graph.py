"""LangGraph StateGraph definition for the Clinical Trial Matcher."""

from __future__ import annotations

import logging
import os

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.graph.state import TrialMatchState
from src.graph.nodes.intake import intake_node
from src.graph.nodes.search import search_node
from src.graph.nodes.eligibility import eligibility_node
from src.graph.nodes.ranker import ranker_node
from src.graph.nodes.human_review import human_review_node

logger = logging.getLogger(__name__)


# --- Routing functions ---


def route_after_intake(state: TrialMatchState) -> str:
    if state.get("clarifications_needed"):
        return "human_review"
    return "search_agent"


def route_after_ranking(state: TrialMatchState) -> str:
    if state.get("clarifications_needed"):
        return "human_review"
    return END


# --- Checkpointer ---


def _create_checkpointer():
    """Create checkpointer based on environment. PostgresSaver if DATABASE_URL is set."""
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver

            checkpointer = PostgresSaver.from_conn_string(db_url)
            checkpointer.setup()
            logger.info("Using PostgresSaver checkpointer")
            return checkpointer
        except Exception as e:
            logger.warning("PostgresSaver setup failed, falling back to MemorySaver: %s", e)
    return MemorySaver()


# --- Graph definition ---

builder = StateGraph(TrialMatchState)

# Nodes
builder.add_node("intake_agent", intake_node)
builder.add_node("search_agent", search_node)
builder.add_node("eligibility_evaluator", eligibility_node)
builder.add_node("ranker_agent", ranker_node)
builder.add_node("human_review", human_review_node)

# Edges
builder.add_edge(START, "intake_agent")
builder.add_conditional_edges(
    "intake_agent",
    route_after_intake,
    {"search_agent": "search_agent", "human_review": "human_review"},
)
builder.add_edge("search_agent", "eligibility_evaluator")
builder.add_edge("eligibility_evaluator", "ranker_agent")
builder.add_conditional_edges(
    "ranker_agent",
    route_after_ranking,
    {"human_review": "human_review", END: END},
)
# human_review uses Command(goto=...) for dynamic re-entry — no static edge needed

# Compile with checkpointer and store
checkpointer = _create_checkpointer()
store = InMemoryStore()
graph = builder.compile(checkpointer=checkpointer, store=store)
