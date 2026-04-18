"""Tests for the Intake Agent node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.graph.state import PatientProfile


class TestIntakeNode:
    @pytest.mark.asyncio
    async def test_successful_extraction(self, empty_state, mock_intake_llm):
        from src.graph.nodes.intake import intake_node

        result = await intake_node(empty_state)

        assert result["patient_profile"] is not None
        assert result["patient_profile"].age == 55
        assert result["patient_profile"].diagnosis == "Non-small cell lung cancer"
        assert result["clarifications_needed"] == []
        assert result["current_node"] == "intake_agent"

    @pytest.mark.asyncio
    async def test_missing_age_triggers_clarification(self, empty_state):
        profile_no_age = PatientProfile(age=0, sex="male", diagnosis="NSCLC")
        with patch("src.graph.nodes.intake.structured_llm") as mock:
            mock.ainvoke = AsyncMock(return_value=profile_no_age)
            from src.graph.nodes.intake import intake_node

            result = await intake_node(empty_state)

        assert len(result["clarifications_needed"]) == 1
        assert "age" in result["clarifications_needed"][0].question

    @pytest.mark.asyncio
    async def test_missing_diagnosis_triggers_clarification(self, empty_state):
        profile_no_dx = PatientProfile(age=55, sex="male", diagnosis="")
        with patch("src.graph.nodes.intake.structured_llm") as mock:
            mock.ainvoke = AsyncMock(return_value=profile_no_dx)
            from src.graph.nodes.intake import intake_node

            result = await intake_node(empty_state)

        assert len(result["clarifications_needed"]) == 1
        assert "diagnosis" in result["clarifications_needed"][0].question

    @pytest.mark.asyncio
    async def test_missing_both_triggers_combined_clarification(self, empty_state):
        profile_missing = PatientProfile(age=0, sex="unknown", diagnosis="")
        with patch("src.graph.nodes.intake.structured_llm") as mock:
            mock.ainvoke = AsyncMock(return_value=profile_missing)
            from src.graph.nodes.intake import intake_node

            result = await intake_node(empty_state)

        assert len(result["clarifications_needed"]) == 1
        question = result["clarifications_needed"][0].question
        assert "age" in question
        assert "diagnosis" in question

    @pytest.mark.asyncio
    async def test_input_truncation(self, empty_state, mock_intake_llm):
        from src.graph.nodes.intake import MAX_INPUT_LENGTH, intake_node

        empty_state["raw_input"] = "x" * (MAX_INPUT_LENGTH + 1000)
        await intake_node(empty_state)

        call_args = mock_intake_llm.ainvoke.call_args[0][0]
        human_msg = call_args[1].content
        # The formatted prompt should contain truncated input
        assert len(human_msg) < MAX_INPUT_LENGTH + 200  # prompt template overhead

    @pytest.mark.asyncio
    async def test_clarification_responses_merged(self, empty_state, mock_intake_llm):
        from src.graph.state import ClarificationResponse
        from src.graph.nodes.intake import intake_node

        empty_state["clarifications_received"] = [
            ClarificationResponse(question_id="age", answer="55 years old")
        ]
        await intake_node(empty_state)

        call_args = mock_intake_llm.ainvoke.call_args[0][0]
        human_msg = call_args[1].content
        assert "55 years old" in human_msg
