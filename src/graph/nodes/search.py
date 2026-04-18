"""Search Agent — queries ClinicalTrials.gov for matching trials."""

from __future__ import annotations

import httpx
from langsmith import traceable
from tenacity import RetryError

from src.graph.state import TrialMatchState
from src.tools.clinical_trials_api import search_trials
from src.utils.retry import api_retry


@api_retry
async def _search_with_retry(condition: str, location: str | None, page_size: int):
    return await search_trials(condition=condition, location=location, page_size=page_size)


@traceable(name="search_agent", metadata={"node_type": "api_call"})
async def search_node(state: TrialMatchState) -> dict:
    profile = state["patient_profile"]
    assert profile is not None, "search_node requires a patient_profile"

    # Build a richer query using biomarkers and stage when available
    query_parts = [profile.diagnosis]
    if profile.stage:
        query_parts.append(profile.stage)
    condition_query = " ".join(query_parts)

    try:
        trials = await _search_with_retry(
            condition=condition_query,
            location=profile.location,
            page_size=20,
        )
        return {
            "candidate_trials": trials,
            "current_node": "search_agent",
        }
    except (httpx.HTTPError, RetryError) as e:
        return {
            "candidate_trials": [],
            "error_log": [f"ClinicalTrials.gov API failed after retries: {e}"],
            "current_node": "search_agent",
        }
