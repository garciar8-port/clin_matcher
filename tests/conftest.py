"""Shared fixtures and LLM mock harness for deterministic, offline tests."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.graph.nodes.eligibility import CriterionAssessment, EligibilityOutput
from src.graph.state import (
    CriterionResult,
    PatientProfile,
    Trial,
    TrialEvaluation,
    TrialMatchState,
)

# --- Sample data fixtures ---


@pytest.fixture
def sample_profile() -> PatientProfile:
    return PatientProfile(
        age=55,
        sex="male",
        diagnosis="Non-small cell lung cancer",
        stage="III",
        prior_therapies=["pembrolizumab"],
        biomarkers=["PD-L1 high"],
        performance_status="ECOG 1",
        comorbidities=[],
        location="Houston, TX",
    )


@pytest.fixture
def sample_profile_minimal() -> PatientProfile:
    return PatientProfile(
        age=42,
        sex="female",
        diagnosis="Breast cancer",
    )


@pytest.fixture
def sample_trials() -> list[Trial]:
    recent = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    older = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    return [
        Trial(
            nct_id="NCT00000001",
            title="Phase III NSCLC Immunotherapy Trial",
            phase="PHASE3",
            status="RECRUITING",
            sponsor="National Cancer Institute",
            conditions=["Non-small Cell Lung Cancer"],
            inclusion_criteria="Age >= 18\nDiagnosis of NSCLC stage III or IV\nECOG 0-2",
            exclusion_criteria="Active autoimmune disease\nPrior anti-PD-1 therapy within 6 months",
            locations=[{"facility": "MD Anderson", "city": "Houston", "state": "TX", "country": "US"}],
            last_updated=recent,
        ),
        Trial(
            nct_id="NCT00000002",
            title="Phase II Targeted Therapy for Lung Cancer",
            phase="PHASE2",
            status="RECRUITING",
            sponsor="Genentech",
            conditions=["Lung Cancer"],
            inclusion_criteria="Age >= 18\nConfirmed NSCLC\nEGFR mutation positive",
            exclusion_criteria="Brain metastases\nPrior EGFR inhibitor therapy",
            locations=[{"facility": "Mayo Clinic", "city": "Rochester", "state": "MN", "country": "US"}],
            last_updated=older,
        ),
        Trial(
            nct_id="NCT00000003",
            title="Phase I Novel Agent for Solid Tumors",
            phase="PHASE1",
            status="RECRUITING",
            sponsor="Pfizer",
            conditions=["Solid Tumors"],
            inclusion_criteria="Age >= 18\nAdvanced solid tumor\nExhausted standard therapies",
            exclusion_criteria="ECOG > 2\nActive infection",
            locations=[{"facility": "Memorial Sloan Kettering", "city": "New York", "state": "NY", "country": "US"}],
            last_updated=recent,
        ),
    ]


@pytest.fixture
def sample_evaluations() -> list[TrialEvaluation]:
    return [
        TrialEvaluation(
            nct_id="NCT00000001",
            criteria_met=[
                CriterionResult(criterion_text="Age >= 18", met=True, reasoning="Patient is 55"),
                CriterionResult(criterion_text="NSCLC stage III or IV", met=True, reasoning="Stage III NSCLC"),
                CriterionResult(criterion_text="ECOG 0-2", met=True, reasoning="ECOG 1"),
            ],
            criteria_failed=[],
            criteria_uncertain=[
                CriterionResult(criterion_text="Prior anti-PD-1 within 6 months", met=None, reasoning="Had pembrolizumab but timing unknown"),
            ],
            eligible="yes",
            reasoning="Meets all inclusion criteria; one exclusion uncertain.",
        ),
        TrialEvaluation(
            nct_id="NCT00000002",
            criteria_met=[
                CriterionResult(criterion_text="Age >= 18", met=True, reasoning="Patient is 55"),
                CriterionResult(criterion_text="Confirmed NSCLC", met=True, reasoning="Diagnosed with NSCLC"),
            ],
            criteria_failed=[
                CriterionResult(criterion_text="EGFR mutation positive", met=False, reasoning="No EGFR mutation reported"),
            ],
            criteria_uncertain=[],
            eligible="no",
            reasoning="Missing required EGFR mutation.",
        ),
        TrialEvaluation(
            nct_id="NCT00000003",
            criteria_met=[
                CriterionResult(criterion_text="Age >= 18", met=True, reasoning="Patient is 55"),
                CriterionResult(criterion_text="Advanced solid tumor", met=True, reasoning="Stage III NSCLC"),
            ],
            criteria_failed=[],
            criteria_uncertain=[
                CriterionResult(criterion_text="Exhausted standard therapies", met=None, reasoning="Only one prior therapy"),
            ],
            eligible="maybe",
            reasoning="Meets basic criteria but unclear if standard therapies exhausted.",
        ),
    ]


@pytest.fixture
def sample_eligibility_output() -> EligibilityOutput:
    return EligibilityOutput(
        criteria_assessments=[
            CriterionAssessment(criterion_text="Age >= 18", met=True, reasoning="Patient is 55"),
            CriterionAssessment(criterion_text="NSCLC stage III or IV", met=True, reasoning="Stage III"),
            CriterionAssessment(criterion_text="ECOG 0-2", met=True, reasoning="ECOG 1"),
            CriterionAssessment(criterion_text="Active autoimmune disease", met=False, reasoning="Not reported"),
        ],
        overall_eligible="yes",
        overall_reasoning="Patient meets all key criteria.",
    )


@pytest.fixture
def sample_ctgov_response() -> dict:
    """Realistic ClinicalTrials.gov API v2 response."""
    return {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {
                        "nctId": "NCT06000001",
                        "briefTitle": "Testing Drug X in NSCLC",
                    },
                    "statusModule": {
                        "overallStatus": "RECRUITING",
                        "lastUpdatePostDate": {"date": "2026-04-01"},
                    },
                    "designModule": {"phases": ["PHASE3"]},
                    "sponsorCollaboratorsModule": {
                        "leadSponsor": {"name": "Acme Pharma"}
                    },
                    "eligibilityModule": {
                        "eligibilityCriteria": (
                            "Inclusion Criteria:\n"
                            "- Age >= 18\n"
                            "- Confirmed NSCLC\n\n"
                            "Exclusion Criteria:\n"
                            "- Active infection\n"
                            "- Pregnant or nursing"
                        )
                    },
                    "conditionsModule": {"conditions": ["Non-Small Cell Lung Cancer"]},
                    "contactsLocationsModule": {
                        "locations": [
                            {
                                "facility": "Test Hospital",
                                "city": "Houston",
                                "state": "Texas",
                                "country": "United States",
                            }
                        ]
                    },
                }
            }
        ]
    }


@pytest.fixture
def empty_state(sample_profile) -> TrialMatchState:
    """A minimal valid state for testing nodes."""
    return {
        "raw_input": "55yo male, stage III NSCLC, prior pembrolizumab, ECOG 1",
        "patient_profile": sample_profile,
        "candidate_trials": [],
        "evaluations": [],
        "rankings": [],
        "clarifications_needed": [],
        "clarifications_received": [],
        "current_node": "",
        "error_log": [],
        "metadata": {},
    }


# --- LLM mock fixtures (CRE-17: recorded-response harness) ---


@pytest.fixture
def mock_intake_llm(sample_profile):
    """Patch the intake agent's structured LLM to return a predetermined profile."""
    with patch("src.graph.nodes.intake.structured_llm") as mock:
        mock.ainvoke = AsyncMock(return_value=sample_profile)
        yield mock


@pytest.fixture
def mock_eligibility_llm(sample_eligibility_output):
    """Patch the eligibility evaluator's structured LLM."""
    with patch("src.graph.nodes.eligibility.structured_llm") as mock:
        mock.ainvoke = AsyncMock(return_value=sample_eligibility_output)
        yield mock


@pytest.fixture
def mock_ranker_llm():
    """Patch the ranker agent's LLM to return a canned summary."""
    mock_response = MagicMock()
    mock_response.content = "Strong match based on diagnosis and stage alignment."
    with patch("src.graph.nodes.ranker.llm") as mock:
        mock.ainvoke = AsyncMock(return_value=mock_response)
        yield mock


@pytest.fixture
def mock_search(sample_trials):
    """Patch search_trials to return sample trials without hitting CT.gov."""
    with patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock:
        mock.return_value = sample_trials
        yield mock
