"""Tests for the Ranker Agent: scoring, ranking, and clarification logic."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.graph.state import CriterionResult, Trial, TrialEvaluation
from src.graph.nodes.ranker import (
    _build_clarification_questions,
    _find_trial,
    _recency_score,
    _score,
)


# --- _recency_score ---


class TestRecencyScore:
    def test_recent_trial(self):
        trial = Trial(
            nct_id="NCT001", title="Test", phase="PHASE3", status="RECRUITING",
            sponsor="X", inclusion_criteria="", exclusion_criteria="",
            last_updated=(datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"),
        )
        score = _recency_score(trial)
        assert score > 0.9  # Very recent

    def test_old_trial(self):
        trial = Trial(
            nct_id="NCT001", title="Test", phase="PHASE3", status="RECRUITING",
            sponsor="X", inclusion_criteria="", exclusion_criteria="",
            last_updated=(datetime.now() - timedelta(days=350)).strftime("%Y-%m-%d"),
        )
        score = _recency_score(trial)
        assert score < 0.1

    def test_invalid_date(self):
        trial = Trial(
            nct_id="NCT001", title="Test", phase="PHASE3", status="RECRUITING",
            sponsor="X", inclusion_criteria="", exclusion_criteria="",
            last_updated="not-a-date",
        )
        assert _recency_score(trial) == 0.3

    def test_empty_date(self):
        trial = Trial(
            nct_id="NCT001", title="Test", phase="PHASE3", status="RECRUITING",
            sponsor="X", inclusion_criteria="", exclusion_criteria="",
            last_updated="",
        )
        assert _recency_score(trial) == 0.3


# --- _score ---


class TestScore:
    def _make_eval(self, met=0, failed=0, uncertain=0, eligible="yes"):
        return TrialEvaluation(
            nct_id="NCT001",
            criteria_met=[
                CriterionResult(criterion_text=f"c{i}", met=True, reasoning="ok")
                for i in range(met)
            ],
            criteria_failed=[
                CriterionResult(criterion_text=f"c{i}", met=False, reasoning="no")
                for i in range(failed)
            ],
            criteria_uncertain=[
                CriterionResult(criterion_text=f"c{i}", met=None, reasoning="?")
                for i in range(uncertain)
            ],
            eligible=eligible,
            reasoning="test",
        )

    def _make_trial(self, phase="PHASE3"):
        return Trial(
            nct_id="NCT001", title="Test", phase=phase, status="RECRUITING",
            sponsor="X", inclusion_criteria="", exclusion_criteria="",
            last_updated=datetime.now().strftime("%Y-%m-%d"),
        )

    def test_perfect_score_phase3(self):
        ev = self._make_eval(met=5, failed=0, uncertain=0)
        trial = self._make_trial("PHASE3")
        score = _score(ev, trial)
        # 0.6 * 1.0 + 0.3 * 1.0 + 0.1 * ~1.0 = ~1.0
        assert score > 0.95

    def test_low_score_phase1_no_criteria(self):
        ev = self._make_eval(met=0, failed=5, uncertain=0)
        trial = self._make_trial("PHASE1")
        score = _score(ev, trial)
        # 0.6 * 0.0 + 0.3 * 0.4 + 0.1 * ~1.0 = ~0.22
        assert score < 0.3

    def test_phase_scoring(self):
        ev = self._make_eval(met=5)
        phase3 = _score(ev, self._make_trial("PHASE3"))
        phase2 = _score(ev, self._make_trial("PHASE2"))
        phase1 = _score(ev, self._make_trial("PHASE1"))
        unknown = _score(ev, self._make_trial("EARLY_PHASE1"))
        assert phase3 > phase2 > phase1 > unknown

    def test_no_criteria_defaults(self):
        ev = self._make_eval(met=0, failed=0, uncertain=0)
        trial = self._make_trial()
        score = _score(ev, trial)
        # criteria_score = 0/max(0,1) = 0 → 0.6*0 + 0.3*1.0 + 0.1*~1.0
        assert 0.3 < score < 0.5


# --- _find_trial ---


class TestFindTrial:
    def test_finds_existing(self, sample_trials):
        result = _find_trial("NCT00000001", sample_trials)
        assert result is not None
        assert result.nct_id == "NCT00000001"

    def test_returns_none_for_missing(self, sample_trials):
        assert _find_trial("NCT99999999", sample_trials) is None


# --- _build_clarification_questions ---


class TestBuildClarificationQuestions:
    def test_builds_questions_from_uncertain(self, sample_profile):
        evals = [
            TrialEvaluation(
                nct_id=f"NCT{i}",
                criteria_met=[],
                criteria_failed=[],
                criteria_uncertain=[
                    CriterionResult(criterion_text=f"Criterion {j}", met=None, reasoning=f"reason {j}")
                    for j in range(5)
                ],
                eligible="maybe",
                reasoning="Many unknowns",
            )
            for i in range(4)
        ]
        questions = _build_clarification_questions(evals, sample_profile)

        assert len(questions) <= 5
        assert all(q.source_node == "ranker_agent" for q in questions)
        assert all("Criterion" in q.question for q in questions)

    def test_deduplicates(self, sample_profile):
        # Same criterion text across multiple evaluations
        evals = [
            TrialEvaluation(
                nct_id=f"NCT{i}",
                criteria_met=[],
                criteria_failed=[],
                criteria_uncertain=[
                    CriterionResult(criterion_text="Same criterion", met=None, reasoning="reason")
                ],
                eligible="maybe",
                reasoning="Unknown",
            )
            for i in range(3)
        ]
        questions = _build_clarification_questions(evals, sample_profile)
        assert len(questions) == 1


# --- ranker_node ---


class TestRankerNode:
    @pytest.mark.asyncio
    async def test_no_eligible_returns_empty(self, empty_state, sample_evaluations):
        from src.graph.nodes.ranker import ranker_node

        # All evaluations are "no"
        for ev in sample_evaluations:
            ev.eligible = "no"
        empty_state["evaluations"] = sample_evaluations
        result = await ranker_node(empty_state)

        assert result["rankings"] == []

    @pytest.mark.asyncio
    async def test_ranks_by_score_descending(
        self, empty_state, sample_trials, sample_evaluations, mock_ranker_llm
    ):
        from src.graph.nodes.ranker import ranker_node

        empty_state["candidate_trials"] = sample_trials
        empty_state["evaluations"] = sample_evaluations
        result = await ranker_node(empty_state)

        rankings = result["rankings"]
        # Only non-"no" evaluations should appear
        assert all(r.evaluation.eligible != "no" for r in rankings)
        # Scores should be descending
        scores = [r.score for r in rankings]
        assert scores == sorted(scores, reverse=True)
        # Ranks should be sequential
        assert [r.rank for r in rankings] == list(range(1, len(rankings) + 1))

    @pytest.mark.asyncio
    async def test_uncertain_heavy_triggers_clarification(self, empty_state, sample_trials):
        from src.graph.nodes.ranker import ranker_node

        # Create evaluations with many uncertain criteria per trial
        heavy_evals = [
            TrialEvaluation(
                nct_id=trial.nct_id,
                criteria_met=[],
                criteria_failed=[],
                criteria_uncertain=[
                    CriterionResult(criterion_text=f"Criterion {j}", met=None, reasoning="?")
                    for j in range(5)
                ],
                eligible="maybe",
                reasoning="Too many unknowns",
            )
            for trial in sample_trials[:4]  # Need >3 uncertain-heavy
        ] + [
            TrialEvaluation(
                nct_id="NCT_EXTRA",
                criteria_met=[],
                criteria_failed=[],
                criteria_uncertain=[
                    CriterionResult(criterion_text=f"Criterion {j}", met=None, reasoning="?")
                    for j in range(5)
                ],
                eligible="maybe",
                reasoning="Too many unknowns",
            )
        ]

        empty_state["candidate_trials"] = sample_trials + [
            Trial(
                nct_id="NCT_EXTRA", title="Extra", phase="PHASE2", status="RECRUITING",
                sponsor="X", inclusion_criteria="", exclusion_criteria="",
                last_updated="2026-01-01",
            )
        ]
        empty_state["evaluations"] = heavy_evals
        result = await ranker_node(empty_state)

        assert len(result["clarifications_needed"]) > 0
        assert result["current_node"] == "ranker_agent"
