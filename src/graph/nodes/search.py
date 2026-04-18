"""Search Agent — queries ClinicalTrials.gov for matching trials."""

from __future__ import annotations

import httpx
from langsmith import traceable

from src.graph.state import TrialMatchState
from src.tools.clinical_trials_api import search_trials

MAX_RETRIES = 3


@traceable(name="search_agent", metadata={"node_type": "api_call"})
async def search_node(state: TrialMatchState) -> dict:
    profile = state["patient_profile"]
    assert profile is not None, "search_node requires a patient_profile"

    # Build a richer query using biomarkers and stage when available
    query_parts = [profile.diagnosis]
    if profile.stage:
        query_parts.append(profile.stage)
    condition_query = " ".join(query_parts)

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            trials = await search_trials(
                condition=condition_query,
                location=profile.location,
                page_size=20,
            )
            return {
                "candidate_trials": trials,
                "current_node": "search_agent",
            }
        except httpx.HTTPError as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    return {
        "candidate_trials": [],
        "error_log": [f"ClinicalTrials.gov API failed after {MAX_RETRIES} attempts: {last_error}"],
        "current_node": "search_agent",
    }
