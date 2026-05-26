"""Pre-filter — deterministic screening of trials before LLM evaluation.

Drops obviously ineligible trials using structured CT.gov fields (no LLM calls):
- Age outside trial's min/max age
- Sex mismatch
- Condition keyword mismatch
"""

from __future__ import annotations

import logging
import re

from langsmith import traceable

from src.graph.state import PatientProfile, Trial, TrialMatchState

logger = logging.getLogger(__name__)

MAX_TRIALS_AFTER_FILTER = 10


def _check_age(profile: PatientProfile, trial: Trial) -> bool:
    """Return False if patient is outside the trial's age range."""
    if trial.minimum_age is not None and profile.age < trial.minimum_age:
        return False
    if trial.maximum_age is not None and profile.age > trial.maximum_age:
        return False
    return True


def _check_sex(profile: PatientProfile, trial: Trial) -> bool:
    """Return False if trial is sex-restricted and patient doesn't match."""
    if trial.sex == "ALL":
        return True
    patient_sex = profile.sex.upper()
    if patient_sex in ("M", "MALE") and trial.sex == "FEMALE":
        return False
    if patient_sex in ("F", "FEMALE") and trial.sex == "MALE":
        return False
    return True


def _check_condition(profile: PatientProfile, trial: Trial) -> bool:
    """Return False if the trial's conditions don't overlap with patient diagnosis."""
    if not trial.conditions:
        return True

    diagnosis_lower = profile.diagnosis.lower()
    diagnosis_terms = set(re.findall(r"\b\w{4,}\b", diagnosis_lower))

    for condition in trial.conditions:
        condition_lower = condition.lower()
        if diagnosis_lower in condition_lower or condition_lower in diagnosis_lower:
            return True
        condition_terms = set(re.findall(r"\b\w{4,}\b", condition_lower))
        if diagnosis_terms & condition_terms:
            return True

    return False


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
            reasons.append(f"age({trial.minimum_age}-{trial.maximum_age})")
        if not _check_sex(profile, trial):
            reasons.append(f"sex({trial.sex})")
        if not _check_condition(profile, trial):
            reasons.append("condition")

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

    kept = kept[:MAX_TRIALS_AFTER_FILTER]

    return {"candidate_trials": kept, "current_node": "prefilter"}
