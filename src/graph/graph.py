"""LangGraph StateGraph definition for the Clinical Trial Matcher."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.graph.nodes.eligibility import eligibility_node
from src.graph.nodes.human_review import human_review_node
from src.graph.nodes.intake import intake_node
from src.graph.nodes.ranker import ranker_node
from src.graph.nodes.search import search_node
from src.graph.state import TrialMatchState

# --- Routing functions ---


def route_after_intake(state: TrialMatchState) -> str:
    if state.get("clarifications_needed"):
        return "human_review"
    return "search_agent"


def route_after_ranking(state: TrialMatchState) -> str:
    if state.get("clarifications_needed"):
        return "human_review"
    return END


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

# Compile without checkpointer/store — LangGraph Platform provides its own.
# For standalone CLI use, __main__.py re-compiles with MemorySaver.
graph = builder.compile()
