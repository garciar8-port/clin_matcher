"""Eligibility Evaluator — evaluates patient against each trial's criteria."""

from __future__ import annotations

import asyncio

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable
from pydantic import BaseModel, Field

from src.graph.state import CriterionResult, Trial, TrialEvaluation, TrialMatchState
from src.prompts.eligibility import ELIGIBILITY_HUMAN, ELIGIBILITY_SYSTEM, ELIGIBILITY_VERSION
from src.utils.retry import llm_retry

MAX_TRIALS = 20

llm = ChatAnthropic(model="claude-sonnet-4-6-20250514")


class EligibilityOutput(BaseModel):
    """Structured output for eligibility evaluation."""

    criteria_assessments: list[CriterionAssessment] = Field(
        description="Assessment of each eligibility criterion"
    )
    overall_eligible: str = Field(
        description="Overall eligibility: 'yes', 'no', or 'maybe'"
    )
    overall_reasoning: str = Field(
        description="Brief overall reasoning for the eligibility determination"
    )


class CriterionAssessment(BaseModel):
    """Assessment of a single criterion."""

    criterion_text: str = Field(description="The criterion being evaluated")
    met: bool | None = Field(
        description="True if met, False if not met, null if uncertain"
    )
    reasoning: str = Field(description="Reasoning for this assessment")


# Fix forward reference
EligibilityOutput.model_rebuild()

structured_llm = llm.with_structured_output(EligibilityOutput)


def _build_evaluation(output: EligibilityOutput, nct_id: str) -> TrialEvaluation:
    """Convert structured LLM output into a TrialEvaluation."""
    met = []
    failed = []
    uncertain = []

    for assessment in output.criteria_assessments:
        result = CriterionResult(
            criterion_text=assessment.criterion_text,
            met=assessment.met,
            reasoning=assessment.reasoning,
        )
        if assessment.met is True:
            met.append(result)
        elif assessment.met is False:
            failed.append(result)
        else:
            uncertain.append(result)

    return TrialEvaluation(
        nct_id=nct_id,
        criteria_met=met,
        criteria_failed=failed,
        criteria_uncertain=uncertain,
        eligible=output.overall_eligible,
        reasoning=output.overall_reasoning,
    )


@llm_retry
async def _evaluate_llm(messages: list) -> EligibilityOutput:
    return await structured_llm.ainvoke(messages)


async def _evaluate_one(profile_json: str, trial: Trial) -> TrialEvaluation:
    """Evaluate a single trial against the patient profile."""
    response = await _evaluate_llm(
        [
            SystemMessage(content=ELIGIBILITY_SYSTEM),
            HumanMessage(
                content=ELIGIBILITY_HUMAN.format(
                    patient=profile_json,
                    inclusion=trial.inclusion_criteria or "Not specified",
                    exclusion=trial.exclusion_criteria or "Not specified",
                )
            ),
        ]
    )
    return _build_evaluation(response, trial.nct_id)


@traceable(name="eligibility_evaluator", metadata={"node_type": "llm_heavy", "prompt_version": ELIGIBILITY_VERSION})
async def eligibility_node(state: TrialMatchState) -> dict:
    profile = state["patient_profile"]
    assert profile is not None
    trials = state["candidate_trials"][:MAX_TRIALS]

    if not trials:
        return {
            "evaluations": [],
            "current_node": "eligibility_evaluator",
        }

    profile_json = profile.model_dump_json(indent=2)
    evaluations = await asyncio.gather(
        *[_evaluate_one(profile_json, trial) for trial in trials]
    )

    return {
        "evaluations": list(evaluations),
        "current_node": "eligibility_evaluator",
    }
