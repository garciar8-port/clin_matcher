"""Data models and state schema for the Clinical Trial Matcher graph."""

from __future__ import annotations

from typing import Annotated, TypedDict

from pydantic import BaseModel

# --- Data Models ---


class PatientProfile(BaseModel):
    """Structured patient profile extracted from free-text input."""

    age: int
    sex: str
    diagnosis: str
    stage: str | None = None
    prior_therapies: list[str] = []
    biomarkers: list[str] = []
    performance_status: str | None = None  # e.g. "ECOG 1"
    comorbidities: list[str] = []
    location: str | None = None  # city/state/zip for proximity ranking


class Trial(BaseModel):
    """A clinical trial from ClinicalTrials.gov."""

    nct_id: str
    title: str
    phase: str
    status: str
    sponsor: str
    conditions: list[str] = []
    inclusion_criteria: str
    exclusion_criteria: str
    locations: list[dict] = []  # {facility, city, state, country}
    last_updated: str


class CriterionResult(BaseModel):
    """Result of evaluating a single eligibility criterion against a patient."""

    criterion_text: str
    met: bool | None = None  # True=met, False=failed, None=uncertain
    reasoning: str


class TrialEvaluation(BaseModel):
    """Full eligibility evaluation of a patient against a single trial."""

    nct_id: str
    criteria_met: list[CriterionResult] = []
    criteria_failed: list[CriterionResult] = []
    criteria_uncertain: list[CriterionResult] = []
    eligible: str  # "yes" | "no" | "maybe"
    reasoning: str


class RankedTrial(BaseModel):
    """A trial with ranking score and plain-language match summary."""

    nct_id: str
    title: str
    rank: int
    score: float
    match_summary: str
    evaluation: TrialEvaluation


class Clarification(BaseModel):
    """A question posed to the user for clarification."""

    source_node: str  # which node is asking
    question: str
    context: str  # why this matters


class ClarificationResponse(BaseModel):
    """User's response to a clarification question."""

    question_id: str
    answer: str


# --- Graph State ---


class TrialMatchState(TypedDict):
    """State that flows through the LangGraph StateGraph."""

    raw_input: str
    patient_profile: PatientProfile | None
    candidate_trials: list[Trial]
    evaluations: list[TrialEvaluation]
    rankings: list[RankedTrial]
    clarifications_needed: list[Clarification]
    clarifications_received: list[ClarificationResponse]
    current_node: str
    error_log: Annotated[list[str], lambda x, y: x + y]
    metadata: dict
