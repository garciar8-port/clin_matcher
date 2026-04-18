"""Prompt versioning registry. Versions logged to LangSmith metadata on every run."""

from __future__ import annotations

from src.prompts.intake import INTAKE_HUMAN, INTAKE_SYSTEM, INTAKE_VERSION
from src.prompts.eligibility import (
    ELIGIBILITY_HUMAN,
    ELIGIBILITY_SYSTEM,
    ELIGIBILITY_VERSION,
)
from src.prompts.ranker import RANKER_SUMMARY_HUMAN, RANKER_SUMMARY_SYSTEM, RANKER_VERSION

PROMPT_REGISTRY: dict[str, dict] = {
    "intake_system": {"version": INTAKE_VERSION, "content": INTAKE_SYSTEM},
    "intake_human": {"version": INTAKE_VERSION, "content": INTAKE_HUMAN},
    "eligibility_system": {"version": ELIGIBILITY_VERSION, "content": ELIGIBILITY_SYSTEM},
    "eligibility_human": {"version": ELIGIBILITY_VERSION, "content": ELIGIBILITY_HUMAN},
    "ranker_summary_system": {"version": RANKER_VERSION, "content": RANKER_SUMMARY_SYSTEM},
    "ranker_summary_human": {"version": RANKER_VERSION, "content": RANKER_SUMMARY_HUMAN},
}


def get_prompt_versions() -> dict[str, str]:
    """Return a flat dict of prompt name → version for LangSmith metadata."""
    return {name: entry["version"] for name, entry in PROMPT_REGISTRY.items()}
