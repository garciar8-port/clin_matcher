"""Intake Agent — extracts a structured PatientProfile from free-text input."""

from __future__ import annotations

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from src.graph.state import Clarification, PatientProfile, TrialMatchState
from src.prompts.intake import INTAKE_HUMAN, INTAKE_SYSTEM

MAX_INPUT_LENGTH = 5_000

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
structured_llm = llm.with_structured_output(PatientProfile)


@traceable(name="intake_agent", metadata={"node_type": "extraction"})
async def intake_node(state: TrialMatchState) -> dict:
    raw_input = state["raw_input"]

    # Merge clarification responses into the input if present
    if state.get("clarifications_received"):
        extra = "\n".join(
            f"Q: {cr.question_id}\nA: {cr.answer}"
            for cr in state["clarifications_received"]
        )
        raw_input = f"{raw_input}\n\nAdditional information:\n{extra}"

    # Input length guard
    if len(raw_input) > MAX_INPUT_LENGTH:
        raw_input = raw_input[:MAX_INPUT_LENGTH]

    profile = await structured_llm.ainvoke(
        [
            SystemMessage(content=INTAKE_SYSTEM),
            HumanMessage(content=INTAKE_HUMAN.format(raw_input=raw_input)),
        ]
    )

    # Validate required fields
    if not profile.diagnosis or not profile.age:
        missing = []
        if not profile.age:
            missing.append("age")
        if not profile.diagnosis:
            missing.append("diagnosis")
        return {
            "clarifications_needed": [
                Clarification(
                    source_node="intake_agent",
                    question=f"Please provide the patient's {' and '.join(missing)}.",
                    context="These fields are required to search for matching trials.",
                )
            ],
            "current_node": "intake_agent",
        }

    return {
        "patient_profile": profile,
        "clarifications_needed": [],
        "current_node": "intake_agent",
    }
