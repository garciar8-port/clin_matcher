"""Pre-filter — deterministic screening of trials before LLM evaluation.

Drops obviously ineligible trials using cheap checks (no LLM calls):
- Age outside trial's age range
- Condition keyword mismatch
- Sex mismatch
"""

from __future__ import annotations

import logging
import re

from langsmith import traceable

from src.graph.state import PatientProfile, Trial, TrialMatchState

logger = logging.getLogger(__name__)

MAX_TRIALS_AFTER_FILTER = 10


def _extract_age_range(criteria_text: str) -> tuple[int | None, int | None]:
    """Extract min/max age from criteria text."""
    min_age = None
    max_age = None

    # Match patterns like "Age >= 18", "at least 18 years", "18 years or older"
    min_patterns = [
        r"age\s*(?:>=?|≥)\s*(\d+)",
        r"(?:at least|minimum|older than)\s*(\d+)\s*years?",
        r"(\d+)\s*years?\s*(?:or older|and older|of age or older)",
    ]
    for pattern in min_patterns:
        match = re.search(pattern, criteria_text, re.IGNORECASE)
        if match:
            min_age = int(match.group(1))
            break

    # Match patterns like "Age <= 75", "no older than 75", "up to 75 years"
    max_patterns = [
        r"age\s*(?:<=?|≤)\s*(\d+)",
        r"(?:no older than|no more than|maximum|up to)\s*(\d+)\s*years?",
        r"(\d+)\s*years?\s*(?:or younger|and younger|of age or younger)",
    ]
    for pattern in max_patterns:
        match = re.search(pattern, criteria_text, re.IGNORECASE)
        if match:
            max_age = int(match.group(1))
            break

    return min_age, max_age


def _check_age(profile: PatientProfile, trial: Trial) -> bool:
    """Return False if patient is clearly outside the trial's age range."""
    criteria = f"{trial.inclusion_criteria} {trial.exclusion_criteria}"
    min_age, max_age = _extract_age_range(criteria)

    if min_age and profile.age < min_age:
        return False
    if max_age and profile.age > max_age:
        return False
    return True


def _check_condition(profile: PatientProfile, trial: Trial) -> bool:
    """Return False if the trial's conditions don't overlap with patient diagnosis."""
    if not trial.conditions:
        return True  # can't filter without condition data

    diagnosis_lower = profile.diagnosis.lower()
    # Extract key terms from diagnosis
    diagnosis_terms = set(re.findall(r"\b\w{4,}\b", diagnosis_lower))

    for condition in trial.conditions:
        condition_lower = condition.lower()
        # Direct substring match
        if diagnosis_lower in condition_lower or condition_lower in diagnosis_lower:
            return True
        # Keyword overlap
        condition_terms = set(re.findall(r"\b\w{4,}\b", condition_lower))
        if diagnosis_terms & condition_terms:
            return True

    return False


def _check_sex(profile: PatientProfile, trial: Trial) -> bool:
    """Return False if trial is sex-restricted and patient doesn't match."""
    criteria = f"{trial.inclusion_criteria} {trial.exclusion_criteria}".lower()

    if profile.sex.lower() in ("male", "m"):
        if re.search(r"\b(female|women)\s+only\b", criteria):
            return False
    elif profile.sex.lower() in ("female", "f"):
        if re.search(r"\b(male|men)\s+only\b", criteria):
            return False
    return True


@traceable(name="prefilter", metadata={"node_type": "deterministic"})
async def prefilter_node(state: TrialMatchState) -> dict:
    profile = state["patient_profile"]
    assert profile is not None
    trials = state["candidate_trials"]

    if not trials:
        return {"candidate_trials": [], "current_node": "prefilter"}

    kept = []
    dropped = []

    for trial in trials:
        reasons = []
        if not _check_age(profile, trial):
            reasons.append("age")
        if not _check_condition(profile, trial):
            reasons.append("condition")
        if not _check_sex(profile, trial):
            reasons.append("sex")

        if reasons:
            dropped.append((trial.nct_id, reasons))
        else:
            kept.append(trial)

    if dropped:
        logger.info(
            "Pre-filter: kept %d/%d trials, dropped %d (%s)",
            len(kept), len(trials), len(dropped),
            ", ".join(f"{nct}:{'+'.join(r)}" for nct, r in dropped),
        )

    # Cap at MAX_TRIALS_AFTER_FILTER to bound LLM cost
    kept = kept[:MAX_TRIALS_AFTER_FILTER]

    return {"candidate_trials": kept, "current_node": "prefilter"}
