"""Intake Agent — extracts a structured PatientProfile from free-text input."""

from __future__ import annotations

import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from src.graph.state import Clarification, PatientProfile, TrialMatchState
from src.prompts.intake import INTAKE_HUMAN, INTAKE_SYSTEM, INTAKE_VERSION
from src.utils.retry import llm_retry

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 5_000

llm = ChatAnthropic(model="claude-haiku-4-5-20251001")
structured_llm = llm.with_structured_output(PatientProfile)


@llm_retry
async def _extract_profile(messages: list) -> PatientProfile:
    return await structured_llm.ainvoke(messages)


@traceable(name="intake_agent", metadata={"node_type": "extraction", "prompt_version": INTAKE_VERSION})
async def intake_node(state: TrialMatchState, store=None) -> dict:
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

    profile = await _extract_profile(
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

    # Save profile to Store for cross-session recall (CRE-33)
    if store:
        try:
            user_id = state.get("metadata", {}).get("user_id", "anonymous")
            store.put(
                ("users", user_id, "patients"),
                f"{profile.age}_{profile.diagnosis}",
                {"profile": profile.model_dump(), "raw_input": state["raw_input"]},
            )
        except Exception as e:
            logger.warning("Failed to save profile to store: %s", e)

    return {
        "patient_profile": profile,
        "clarifications_needed": [],
        "current_node": "intake_agent",
    }
