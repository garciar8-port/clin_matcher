"""Tests for the Search Agent node."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest


class TestSearchNode:
    @pytest.mark.asyncio
    async def test_successful_search(self, empty_state, mock_search, sample_trials):
        from src.graph.nodes.search import search_node

        result = await search_node(empty_state)

        assert len(result["candidate_trials"]) == len(sample_trials)
        assert result["current_node"] == "search_agent"

    @pytest.mark.asyncio
    async def test_builds_query_with_stage(self, empty_state):
        with patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock:
            mock.return_value = []
            from src.graph.nodes.search import search_node

            await search_node(empty_state)

            call_kwargs = mock.call_args[1]
            assert "III" in call_kwargs["condition"]
            assert "Non-small cell lung cancer" in call_kwargs["condition"]

    @pytest.mark.asyncio
    async def test_passes_location(self, empty_state):
        with patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock:
            mock.return_value = []
            from src.graph.nodes.search import search_node

            await search_node(empty_state)

            call_kwargs = mock.call_args[1]
            assert call_kwargs["location"] == "Houston, TX"

    @pytest.mark.asyncio
    async def test_api_failure_after_retries(self, empty_state):
        with patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock:
            mock.side_effect = httpx.HTTPError("Connection failed")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                from src.graph.nodes.search import search_node

                result = await search_node(empty_state)

        assert result["candidate_trials"] == []
        assert len(result["error_log"]) == 1
        assert "failed after retries" in result["error_log"][0]

    @pytest.mark.asyncio
    async def test_retry_then_success(self, empty_state, sample_trials):
        with patch("src.graph.nodes.search.search_trials", new_callable=AsyncMock) as mock:
            mock.side_effect = [httpx.HTTPError("timeout"), sample_trials]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                from src.graph.nodes.search import search_node

                result = await search_node(empty_state)

        assert len(result["candidate_trials"]) == len(sample_trials)
        assert mock.call_count == 2
