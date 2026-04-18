"""Tests for graph routing functions."""

from __future__ import annotations

from langgraph.graph import END

from src.graph.graph import route_after_intake, route_after_ranking
from src.graph.state import Clarification


class TestRouteAfterIntake:
    def test_routes_to_search_when_no_clarifications(self):
        state = {"clarifications_needed": []}
        assert route_after_intake(state) == "search_agent"

    def test_routes_to_search_when_key_missing(self):
        state = {}
        assert route_after_intake(state) == "search_agent"

    def test_routes_to_human_review_when_clarifications(self):
        state = {
            "clarifications_needed": [
                Clarification(
                    source_node="intake_agent",
                    question="What is the patient's age?",
                    context="Required for matching.",
                )
            ]
        }
        assert route_after_intake(state) == "human_review"


class TestRouteAfterRanking:
    def test_routes_to_end_when_no_clarifications(self):
        state = {"clarifications_needed": []}
        assert route_after_ranking(state) == END

    def test_routes_to_end_when_key_missing(self):
        state = {}
        assert route_after_ranking(state) == END

    def test_routes_to_human_review_when_clarifications(self):
        state = {
            "clarifications_needed": [
                Clarification(
                    source_node="ranker_agent",
                    question="Clarify prior therapy timing",
                    context="Needed for eligibility.",
                )
            ]
        }
        assert route_after_ranking(state) == "human_review"
