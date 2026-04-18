"""Ranker Agent — scores and ranks eligible trials with match summaries."""

from __future__ import annotations

from datetime import datetime

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import traceable

from src.graph.state import (
    Clarification,
    RankedTrial,
    Trial,
    TrialEvaluation,
    TrialMatchState,
)
from src.prompts.ranker import RANKER_SUMMARY_HUMAN, RANKER_SUMMARY_SYSTEM

llm = ChatAnthropic(model="claude-sonnet-4-6-20250514")


def _recency_score(trial: Trial) -> float:
    """Score based on how recently the trial was updated (0.0–1.0)."""
    try:
        updated = datetime.strptime(trial.last_updated, "%Y-%m-%d")
        days_ago = (datetime.now() - updated).days
        # Within 30 days = 1.0, decays over 365 days
        return max(0.0, 1.0 - (days_ago / 365))
    except (ValueError, TypeError):
        return 0.3  # Default for unparseable dates


def _score(evaluation: TrialEvaluation, trial: Trial) -> float:
    """Compute a weighted match score for a trial."""
    total_criteria = (
        len(evaluation.criteria_met)
        + len(evaluation.criteria_failed)
        + len(evaluation.criteria_uncertain)
    )
    criteria_score = len(evaluation.criteria_met) / max(total_criteria, 1)

    phase_scores = {"PHASE3": 1.0, "PHASE2": 0.7, "PHASE1": 0.4}
    phase_key = trial.phase.upper().replace(" ", "")
    phase_score = phase_scores.get(phase_key, 0.3)

    recency = _recency_score(trial)

    return 0.6 * criteria_score + 0.3 * phase_score + 0.1 * recency


def _find_trial(nct_id: str, trials: list[Trial]) -> Trial | None:
    """Find a trial by NCT ID."""
    for t in trials:
        if t.nct_id == nct_id:
            return t
    return None


def _build_clarification_questions(
    uncertain_heavy: list[TrialEvaluation],
    profile,
) -> list[Clarification]:
    """Build clarification questions from trials with many uncertain criteria."""
    # Collect unique uncertain criteria across trials
    seen = set()
    questions = []
    for ev in uncertain_heavy:
        for criterion in ev.criteria_uncertain:
            text = criterion.criterion_text[:100]
            if text not in seen:
                seen.add(text)
                questions.append(
                    Clarification(
                        source_node="ranker_agent",
                        question=f"Can you clarify: {criterion.criterion_text}",
                        context=criterion.reasoning,
                    )
                )
    return questions[:5]  # Cap at 5 questions


async def _generate_summary(
    profile, trial: Trial, evaluation: TrialEvaluation
) -> str:
    """Generate a plain-language match summary for a patient-trial pair."""
    response = await llm.ainvoke(
        [
            SystemMessage(content=RANKER_SUMMARY_SYSTEM),
            HumanMessage(
                content=RANKER_SUMMARY_HUMAN.format(
                    age=profile.age,
                    sex=profile.sex,
                    diagnosis=profile.diagnosis,
                    stage=profile.stage or "Not specified",
                    biomarkers=", ".join(profile.biomarkers) or "None reported",
                    prior_therapies=", ".join(profile.prior_therapies) or "None reported",
                    performance_status=profile.performance_status or "Not specified",
                    trial_title=trial.title,
                    nct_id=trial.nct_id,
                    phase=trial.phase,
                    criteria_met_count=len(evaluation.criteria_met),
                    criteria_failed_count=len(evaluation.criteria_failed),
                    criteria_uncertain_count=len(evaluation.criteria_uncertain),
                    eligible=evaluation.eligible,
                    reasoning=evaluation.reasoning,
                )
            ),
        ]
    )
    return response.content


@traceable(name="ranker_agent", metadata={"node_type": "llm_light"})
async def ranker_node(state: TrialMatchState) -> dict:
    profile = state["patient_profile"]
    assert profile is not None

    eligible = [e for e in state["evaluations"] if e.eligible != "no"]
    trials = state["candidate_trials"]

    if not eligible:
        return {
            "rankings": [],
            "clarifications_needed": [],
            "current_node": "ranker_agent",
        }

    # Check if too many uncertain criteria — route to human review
    uncertain_heavy = [e for e in eligible if len(e.criteria_uncertain) > 3]
    if len(uncertain_heavy) > 3:
        questions = _build_clarification_questions(uncertain_heavy, profile)
        return {
            "clarifications_needed": questions,
            "current_node": "ranker_agent",
        }

    # Score and rank
    scored = []
    for ev in eligible:
        trial = _find_trial(ev.nct_id, trials)
        if trial:
            scored.append((ev, trial, _score(ev, trial)))

    scored.sort(key=lambda x: x[2], reverse=True)

    # Generate summaries for top results
    rankings = []
    for i, (ev, trial, score) in enumerate(scored):
        summary = await _generate_summary(profile, trial, ev)
        rankings.append(
            RankedTrial(
                nct_id=ev.nct_id,
                title=trial.title,
                rank=i + 1,
                score=round(score, 3),
                match_summary=summary,
                evaluation=ev,
            )
        )

    return {
        "rankings": rankings,
        "clarifications_needed": [],
        "current_node": "ranker_agent",
    }
