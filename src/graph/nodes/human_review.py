"""Human Review node — pauses execution for user clarification via interrupt."""

from __future__ import annotations

from langgraph.types import Command, interrupt
from langsmith import traceable

from src.graph.state import TrialMatchState


@traceable(name="human_review", metadata={"node_type": "interrupt"})
async def human_review_node(state: TrialMatchState) -> Command:
    clarifications = state["clarifications_needed"]

    # Pause execution — state persists via checkpointer
    user_responses = interrupt(clarifications)

    # Route back to the node that asked for clarification
    source = clarifications[0].source_node

    return Command(
        goto=source,
        update={
            "clarifications_received": user_responses,
            "clarifications_needed": [],
        },
    )
