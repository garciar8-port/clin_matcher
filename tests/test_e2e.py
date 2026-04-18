"""End-to-end tests with 5 synthetic patient cases (CRE-22).

Each case runs through the full graph with mocked LLM + API calls,
verifying the pipeline produces correctly structured output.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.graph.state import (
    CriterionResult,
    PatientProfile,
    Trial,
    TrialEvaluation,
    TrialMatchState,
)
from src.graph.nodes.eligibility import CriterionAssessment, EligibilityOutput


# --- Synthetic patient cases ---

SYNTHETIC_PATIENTS = {
    "nsclc_standard": {
        "input": "55yo male, stage III NSCLC, prior pembrolizumab, ECOG 1, PD-L1 high, Houston TX",
        "profile": PatientProfile(
            age=55, sex="male", diagnosis="Non-small cell lung cancer",
            stage="III", prior_therapies=["pembrolizumab"],
            biomarkers=["PD-L1 high"], performance_status="ECOG 1",
            location="Houston, TX",
        ),
    },
    "breast_her2": {
        "input": "42yo female, HER2+ breast cancer stage II, prior trastuzumab and docetaxel, ECOG 0, New York",
        "profile": PatientProfile(
            age=42, sex="female", diagnosis="Breast cancer",
            stage="II", prior_therapies=["trastuzumab", "docetaxel"],
            biomarkers=["HER2+"], performance_status="ECOG 0",
            location="New York, NY",
        ),
    },
    "colorectal_kras": {
        "input": "68yo male, metastatic colorectal cancer, KRAS G12C mutant, prior FOLFOX and bevacizumab, ECOG 2, Chicago",
        "profile": PatientProfile(
            age=68, sex="male", diagnosis="Colorectal cancer",
            stage="IV", prior_therapies=["FOLFOX", "bevacizumab"],
            biomarkers=["KRAS G12C"], performance_status="ECOG 2",
            comorbidities=["liver metastases"], location="Chicago, IL",
        ),
    },
    "melanoma_braf": {
        "input": "35yo female, stage IV melanoma, BRAF V600E, prior ipilimumab and nivolumab, ECOG 1, Los Angeles",
        "profile": PatientProfile(
            age=35, sex="female", diagnosis="Melanoma",
            stage="IV", prior_therapies=["ipilimumab", "nivolumab"],
            biomarkers=["BRAF V600E"], performance_status="ECOG 1",
            location="Los Angeles, CA",
        ),
    },
    "nsclc_treatment_naive": {
        "input": "71yo male, stage II NSCLC, no prior therapy, ECOG 0, EGFR exon 19 deletion, Boston",
        "profile": PatientProfile(
            age=71, sex="male", diagnosis="Non-small cell lung cancer",
            stage="II", prior_therapies=[],
            biomarkers=["EGFR exon 19 deletion"], performance_status="ECOG 0",
            location="Boston, MA",
        ),
    },
}


def _make_mock_trials(condition: str, n: int = 3) -> list[Trial]:
    """Generate n mock trials for a given condition."""
    recent = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    return [
        Trial(
            nct_id=f"NCT_E2E_{i:04d}",
            title=f"Phase {3 - i % 3} {condition} Trial {i}",
            phase=["PHASE3", "PHASE2", "PHASE1"][i % 3],
            status="RECRUITING",
            sponsor=f"Sponsor {i}",
            conditions=[condition],
            inclusion_criteria=f"Age >= 18\nDiagnosis of {condition}",
            exclusion_criteria="Active autoimmune disease",
            locations=[{"facility": f"Hospital {i}", "city": "Test", "state": "TX", "country": "US"}],
            last_updated=recent,
        )
        for i in range(n)
    ]


def _make_mock_eligibility_output(met_count: int = 2, failed_count: int = 0, uncertain_count: int = 0) -> EligibilityOutput:
    assessments = (
        [CriterionAssessment(criterion_text=f"Inc {i}", met=True, reasoning="Met") for i in range(met_count)]
        + [CriterionAssessment(criterion_text=f"Fail {i}", met=False, reasoning="Not met") for i in range(failed_count)]
        + [CriterionAssessment(criterion_text=f"Unc {i}", met=None, reasoning="Unknown") for i in range(uncertain_count)]
    )
    if failed_count > 0:
        eligible = "no"
    elif uncertain_count > 0:
        eligible = "maybe"
    else:
        eligible = "yes"
    return EligibilityOutput(
        criteria_assessments=assessments,
        overall_eligible=eligible,
        overall_reasoning="Automated assessment",
    )


def _build_initial_state(patient_key: str) -> TrialMatchState:
    return {
        "raw_input": SYNTHETIC_PATIENTS[patient_key]["input"],
        "patient_profile": None,
        "candidate_trials": [],
        "evaluations": [],
        "rankings": [],
        "clarifications_needed": [],
        "clarifications_received": [],
        "current_node": "",
        "error_log": [],
        "metadata": {},
    }


async def _run_graph_with_mocks(patient_key: str):
    """Run the full graph pipeline with mocked external calls."""
    patient = SYNTHETIC_PATIENTS[patient_key]
    profile = patient["profile"]
    mock_trials = _make_mock_trials(profile.diagnosis)

    # Mock LLM response for summaries
    mock_summary = MagicMock()
    mock_summary.content = f"Good match for {profile.diagnosis} patient."

    # Eligibility outputs — first trial eligible, second maybe, third no
    elig_outputs = [
        _make_mock_eligibility_output(met_count=3),
        _make_mock_eligibility_output(met_count=1, uncertain_count=2),
        _make_mock_eligibility_output(met_count=0, failed_count=2),
    ]
    elig_call_count = 0

    async def mock_elig_invoke(*args, **kwargs):
        nonlocal elig_call_count
        idx = min(elig_call_count, len(elig_outputs) - 1)
        elig_call_count += 1
        return elig_outputs[idx]

    with (
        patch("src.graph.nodes.intake.structured_llm") as mock_intake,
        patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock_search,
        patch("src.graph.nodes.eligibility.structured_llm") as mock_elig,
        patch("src.graph.nodes.ranker.llm") as mock_ranker,
    ):
        mock_intake.ainvoke = AsyncMock(return_value=profile)
        mock_search.return_value = mock_trials
        mock_elig.ainvoke = AsyncMock(side_effect=mock_elig_invoke)
        mock_ranker.ainvoke = AsyncMock(return_value=mock_summary)

        from src.graph.graph import graph

        config = {"configurable": {"thread_id": f"test_{patient_key}"}}
        initial_state = _build_initial_state(patient_key)

        final_state = None
        async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, updates in event.items():
                if "rankings" in updates:
                    final_state = updates

        return final_state, mock_intake, mock_search, mock_elig, mock_ranker


# --- Tests ---


@pytest.mark.asyncio
class TestE2EPatients:
    async def test_nsclc_standard(self):
        """55yo male, stage III NSCLC — standard oncology case."""
        result, intake, search, elig, ranker = await _run_graph_with_mocks("nsclc_standard")

        assert result is not None
        assert "rankings" in result
        intake.ainvoke.assert_called_once()
        search.assert_called_once()
        assert elig.ainvoke.call_count == 3

    async def test_breast_her2(self):
        """42yo female, HER2+ breast cancer — targeted therapy candidate."""
        result, *_ = await _run_graph_with_mocks("breast_her2")

        assert result is not None
        rankings = result.get("rankings", [])
        # NCT_E2E_0002 (failed all criteria) should not appear
        nct_ids = [r.nct_id for r in rankings]
        assert "NCT_E2E_0002" not in nct_ids

    async def test_colorectal_kras(self):
        """68yo male, metastatic CRC with KRAS — complex case."""
        result, *_ = await _run_graph_with_mocks("colorectal_kras")

        assert result is not None
        rankings = result.get("rankings", [])
        # Should have ranked trials with scores
        for r in rankings:
            assert 0.0 <= r.score <= 1.0
            assert r.rank >= 1

    async def test_melanoma_braf(self):
        """35yo female, stage IV melanoma, BRAF V600E — immunotherapy experienced."""
        result, _, search, *_ = await _run_graph_with_mocks("melanoma_braf")

        assert result is not None
        # Search should have been called with melanoma
        call_kwargs = search.call_args[1]
        assert "Melanoma" in call_kwargs["condition"]

    async def test_nsclc_treatment_naive(self):
        """71yo male, early NSCLC, treatment naive — should match well."""
        result, *_ = await _run_graph_with_mocks("nsclc_treatment_naive")

        assert result is not None
        rankings = result.get("rankings", [])
        # All eligible trials should have summaries
        for r in rankings:
            assert r.match_summary != ""
            assert r.evaluation is not None


@pytest.mark.asyncio
class TestE2EPipelineIntegrity:
    async def test_all_nodes_execute_in_order(self):
        """Verify each node executes and updates current_node."""
        patient = SYNTHETIC_PATIENTS["nsclc_standard"]
        profile = patient["profile"]
        mock_trials = _make_mock_trials(profile.diagnosis, n=2)
        elig_output = _make_mock_eligibility_output(met_count=2)

        mock_summary = MagicMock()
        mock_summary.content = "Match summary."

        nodes_visited = []

        with (
            patch("src.graph.nodes.intake.structured_llm") as mock_intake,
            patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock_search,
            patch("src.graph.nodes.eligibility.structured_llm") as mock_elig,
            patch("src.graph.nodes.ranker.llm") as mock_ranker,
        ):
            mock_intake.ainvoke = AsyncMock(return_value=profile)
            mock_search.return_value = mock_trials
            mock_elig.ainvoke = AsyncMock(return_value=elig_output)
            mock_ranker.ainvoke = AsyncMock(return_value=mock_summary)

            from src.graph.graph import graph

            config = {"configurable": {"thread_id": "test_order"}}
            initial = _build_initial_state("nsclc_standard")

            async for event in graph.astream(initial, config=config, stream_mode="updates"):
                for node_name in event:
                    nodes_visited.append(node_name)

        assert nodes_visited == [
            "intake_agent",
            "search_agent",
            "eligibility_evaluator",
            "ranker_agent",
        ]

    async def test_error_in_search_still_completes(self):
        """If search fails, graph should still reach ranker with empty results."""
        patient = SYNTHETIC_PATIENTS["nsclc_standard"]
        profile = patient["profile"]

        mock_summary = MagicMock()
        mock_summary.content = "No trials found."

        import httpx

        with (
            patch("src.graph.nodes.intake.structured_llm") as mock_intake,
            patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock_search,
            patch("src.graph.nodes.eligibility.structured_llm") as mock_elig,
            patch("src.graph.nodes.ranker.llm") as mock_ranker,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_intake.ainvoke = AsyncMock(return_value=profile)
            mock_search.side_effect = httpx.HTTPError("API down")
            mock_elig.ainvoke = AsyncMock()  # Should not be called
            mock_ranker.ainvoke = AsyncMock(return_value=mock_summary)

            from src.graph.graph import graph

            config = {"configurable": {"thread_id": "test_search_error"}}
            initial = _build_initial_state("nsclc_standard")

            nodes_visited = []
            async for event in graph.astream(initial, config=config, stream_mode="updates"):
                for node_name in event:
                    nodes_visited.append(node_name)

            assert "search_agent" in nodes_visited
            assert "ranker_agent" in nodes_visited
