"""Tests for ClinicalTrials.gov API client internals: parsing, caching, criteria splitting."""

from __future__ import annotations

import time

import pytest

from src.tools.clinical_trials_api import (
    _cache,
    _cache_key,
    _get_cached,
    _parse_trial,
    _set_cached,
    _split_criteria,
    search_trials,
)

# --- _split_criteria ---


class TestSplitCriteria:
    def test_basic_split(self):
        raw = (
            "Inclusion Criteria:\n- Age >= 18\n- Confirmed diagnosis\n\n"
            "Exclusion Criteria:\n- Active infection\n- Pregnancy"
        )
        inc, exc = _split_criteria(raw)
        assert "Age >= 18" in inc
        assert "Active infection" in exc
        assert "Inclusion" not in inc
        assert "Exclusion" not in exc

    def test_no_exclusion(self):
        raw = "Inclusion Criteria:\n- Age >= 18\n- ECOG 0-1"
        inc, exc = _split_criteria(raw)
        assert "Age >= 18" in inc
        assert exc == ""

    def test_empty_input(self):
        inc, exc = _split_criteria("")
        assert inc == ""
        assert exc == ""

    def test_none_input(self):
        inc, exc = _split_criteria(None)
        assert inc == ""
        assert exc == ""

    def test_header_stripping_variants(self):
        raw = "inclusion criteria: be adult\nexclusion criteria: be sick"
        inc, exc = _split_criteria(raw)
        assert inc == "be adult"
        assert "be sick" in exc

    def test_exclusion_keyword_without_criteria(self):
        raw = "Must be adult\nExclusion: prior chemotherapy"
        inc, exc = _split_criteria(raw)
        assert "adult" in inc
        assert "chemotherapy" in exc


# --- _parse_trial ---


class TestParseTrial:
    def test_parses_complete_study(self, sample_ctgov_response):
        study = sample_ctgov_response["studies"][0]
        trial = _parse_trial(study)

        assert trial.nct_id == "NCT06000001"
        assert trial.title == "Testing Drug X in NSCLC"
        assert trial.phase == "PHASE3"
        assert trial.status == "RECRUITING"
        assert trial.sponsor == "Acme Pharma"
        assert "Non-Small Cell Lung Cancer" in trial.conditions
        assert "Age >= 18" in trial.inclusion_criteria
        assert "Active infection" in trial.exclusion_criteria
        assert trial.locations[0]["city"] == "Houston"
        assert trial.last_updated == "2026-04-01"

    def test_handles_missing_fields(self):
        study = {"protocolSection": {}}
        trial = _parse_trial(study)

        assert trial.nct_id == ""
        assert trial.title == ""
        assert trial.phase == "N/A"
        assert trial.sponsor == "Unknown"
        assert trial.locations == []

    def test_handles_multiple_phases(self):
        study = {
            "protocolSection": {
                "designModule": {"phases": ["PHASE1", "PHASE2"]},
            }
        }
        trial = _parse_trial(study)
        assert trial.phase == "PHASE1"


# --- Cache ---


class TestCache:
    def setup_method(self):
        _cache.clear()

    def test_set_and_get(self, sample_trials):
        key = "test_key"
        _set_cached(key, sample_trials)
        result = _get_cached(key)
        assert result is not None
        assert len(result) == len(sample_trials)

    def test_get_missing_key(self):
        assert _get_cached("nonexistent") is None

    def test_cache_expiry(self, sample_trials):
        key = "expiring"
        _set_cached(key, sample_trials)
        # Manually expire by setting old timestamp
        _cache[key] = (time.time() - 90_000, sample_trials)
        assert _get_cached(key) is None
        assert key not in _cache  # Entry cleaned up

    def test_cache_key_deterministic(self):
        params_a = {"query.cond": "NSCLC", "pageSize": 20}
        params_b = {"pageSize": 20, "query.cond": "NSCLC"}
        assert _cache_key(params_a) == _cache_key(params_b)


# --- search_trials ---


class TestSearchTrials:
    def setup_method(self):
        _cache.clear()

    @pytest.mark.asyncio
    async def test_returns_trials_from_cache(self, sample_ctgov_response):
        """Test that search_trials returns correct Trial objects via cache."""
        # Parse expected trials and cache them directly
        from src.tools.clinical_trials_api import _parse_trial
        expected = [_parse_trial(s) for s in sample_ctgov_response["studies"]]
        params = {"query.cond": "NSCLC direct", "filter.overallStatus": "RECRUITING", "pageSize": 20}
        _set_cached(_cache_key(params), expected)

        trials = await search_trials("NSCLC direct")
        assert len(trials) == 1
        assert trials[0].nct_id == "NCT06000001"

    @pytest.mark.asyncio
    async def test_uses_cache(self, sample_trials):
        """Test that repeated calls with same params use cache."""
        _set_cached(
            _cache_key({"query.cond": "cached", "filter.overallStatus": "RECRUITING", "pageSize": 20}),
            sample_trials,
        )
        result = await search_trials("cached")
        assert len(result) == len(sample_trials)

    @pytest.mark.asyncio
    async def test_location_adds_param(self):
        """Test that location is included in cache key params."""
        params_no_loc = {"query.cond": "test", "filter.overallStatus": "RECRUITING", "pageSize": 20}
        params_with_loc = {"query.cond": "test", "filter.overallStatus": "RECRUITING", "pageSize": 20, "query.locn": "Houston, TX"}
        assert _cache_key(params_no_loc) != _cache_key(params_with_loc)
