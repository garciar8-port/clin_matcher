"""Tests for the Eligibility Evaluator node internals."""

from __future__ import annotations

import pytest

from src.graph.nodes.eligibility import (
    CriterionAssessment,
    EligibilityOutput,
    _build_evaluation,
)


class TestBuildEvaluation:
    def test_all_met(self):
        output = EligibilityOutput(
            criteria_assessments=[
                CriterionAssessment(criterion_text="Age >= 18", met=True, reasoning="ok"),
                CriterionAssessment(criterion_text="ECOG 0-2", met=True, reasoning="ok"),
            ],
            overall_eligible="yes",
            overall_reasoning="All good",
        )
        ev = _build_evaluation(output, "NCT001")

        assert ev.nct_id == "NCT001"
        assert len(ev.criteria_met) == 2
        assert len(ev.criteria_failed) == 0
        assert len(ev.criteria_uncertain) == 0
        assert ev.eligible == "yes"

    def test_mixed_results(self):
        output = EligibilityOutput(
            criteria_assessments=[
                CriterionAssessment(criterion_text="Age >= 18", met=True, reasoning="ok"),
                CriterionAssessment(criterion_text="EGFR+", met=False, reasoning="not reported"),
                CriterionAssessment(criterion_text="Prior therapy", met=None, reasoning="unclear"),
            ],
            overall_eligible="maybe",
            overall_reasoning="Mixed",
        )
        ev = _build_evaluation(output, "NCT002")

        assert len(ev.criteria_met) == 1
        assert len(ev.criteria_failed) == 1
        assert len(ev.criteria_uncertain) == 1
        assert ev.eligible == "maybe"

    def test_all_uncertain(self):
        output = EligibilityOutput(
            criteria_assessments=[
                CriterionAssessment(criterion_text="Lab values", met=None, reasoning="no data"),
                CriterionAssessment(criterion_text="Prior tx", met=None, reasoning="no data"),
            ],
            overall_eligible="maybe",
            overall_reasoning="Insufficient information",
        )
        ev = _build_evaluation(output, "NCT003")

        assert len(ev.criteria_met) == 0
        assert len(ev.criteria_uncertain) == 2

    def test_all_failed(self):
        output = EligibilityOutput(
            criteria_assessments=[
                CriterionAssessment(criterion_text="Age >= 65", met=False, reasoning="Too young"),
                CriterionAssessment(criterion_text="ECOG 0", met=False, reasoning="ECOG 1"),
            ],
            overall_eligible="no",
            overall_reasoning="Does not meet criteria",
        )
        ev = _build_evaluation(output, "NCT004")

        assert len(ev.criteria_failed) == 2
        assert ev.eligible == "no"


class TestEligibilityNode:
    @pytest.mark.asyncio
    async def test_empty_trials_returns_empty(self, empty_state):
        from src.graph.nodes.eligibility import eligibility_node

        empty_state["candidate_trials"] = []
        result = await eligibility_node(empty_state)

        assert result["evaluations"] == []

    @pytest.mark.asyncio
    async def test_evaluates_all_trials(self, empty_state, sample_trials, mock_eligibility_llm):
        from src.graph.nodes.eligibility import eligibility_node

        empty_state["candidate_trials"] = sample_trials
        result = await eligibility_node(empty_state)

        assert len(result["evaluations"]) == len(sample_trials)
        assert mock_eligibility_llm.ainvoke.call_count == len(sample_trials)

    @pytest.mark.asyncio
    async def test_caps_at_max_trials(self, empty_state, sample_trials, mock_eligibility_llm):
        from src.graph.nodes.eligibility import MAX_TRIALS, eligibility_node

        # Create more trials than MAX_TRIALS
        many_trials = sample_trials * 10  # 30 trials
        empty_state["candidate_trials"] = many_trials
        result = await eligibility_node(empty_state)

        assert len(result["evaluations"]) == MAX_TRIALS
