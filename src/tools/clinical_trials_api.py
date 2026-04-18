"""ClinicalTrials.gov API v2 client with caching."""

from __future__ import annotations

import time
from urllib.parse import urlencode

import aiohttp

from src.graph.state import Trial

CTGOV_BASE = "https://clinicaltrials.gov/api/v2"

# Simple in-memory cache with TTL (24 hours)
_cache: dict[str, tuple[float, list[Trial]]] = {}
CACHE_TTL = 86_400  # 24 hours


def _cache_key(params: dict) -> str:
    return str(sorted(params.items()))


def _get_cached(key: str) -> list[Trial] | None:
    if key in _cache:
        timestamp, trials = _cache[key]
        if time.time() - timestamp < CACHE_TTL:
            return trials
        del _cache[key]
    return None


def _set_cached(key: str, trials: list[Trial]) -> None:
    _cache[key] = (time.time(), trials)


def _split_criteria(raw: str) -> tuple[str, str]:
    """Split eligibility criteria text into inclusion and exclusion sections."""
    raw = raw or ""
    lower = raw.lower()

    exc_idx = lower.find("exclusion criteria")
    if exc_idx == -1:
        exc_idx = lower.find("exclusion")

    if exc_idx != -1:
        inclusion = raw[:exc_idx].strip()
        exclusion = raw[exc_idx:].strip()
    else:
        inclusion = raw.strip()
        exclusion = ""

    # Strip headers
    for prefix in ("inclusion criteria:", "inclusion criteria", "inclusion:"):
        if inclusion.lower().startswith(prefix):
            inclusion = inclusion[len(prefix):].strip()

    for prefix in ("exclusion criteria:", "exclusion criteria", "exclusion:"):
        if exclusion.lower().startswith(prefix):
            exclusion = exclusion[len(prefix):].strip()

    return inclusion, exclusion


def _parse_trial(study: dict) -> Trial:
    """Parse a ClinicalTrials.gov API v2 study object into a Trial model."""
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    eligibility = proto.get("eligibilityModule", {})
    conditions_mod = proto.get("conditionsModule", {})
    contacts_loc = proto.get("contactsLocationsModule", {})

    # Locations
    locations = []
    for loc in contacts_loc.get("locations", []):
        locations.append({
            "facility": loc.get("facility", ""),
            "city": loc.get("city", ""),
            "state": loc.get("state", ""),
            "country": loc.get("country", ""),
        })

    # Phase
    phases = design.get("phases", [])
    phase = phases[0] if phases else "N/A"

    # Criteria split
    criteria_text = eligibility.get("eligibilityCriteria", "")
    inclusion, exclusion = _split_criteria(criteria_text)

    # Sponsor
    lead = sponsor_mod.get("leadSponsor", {})
    sponsor = lead.get("name", "Unknown")

    return Trial(
        nct_id=ident.get("nctId", ""),
        title=ident.get("briefTitle", ""),
        phase=phase,
        status=status_mod.get("overallStatus", ""),
        sponsor=sponsor,
        conditions=conditions_mod.get("conditions", []),
        inclusion_criteria=inclusion,
        exclusion_criteria=exclusion,
        locations=locations,
        last_updated=status_mod.get("lastUpdatePostDate", {}).get("date", ""),
    )


async def search_trials(
    condition: str,
    location: str | None = None,
    page_size: int = 20,
) -> list[Trial]:
    """Search ClinicalTrials.gov for recruiting trials matching the condition."""
    params: dict[str, str | int] = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING",
        "pageSize": page_size,
    }

    if location:
        params["query.locn"] = location

    # Check cache
    key = _cache_key(params)
    cached = _get_cached(key)
    if cached is not None:
        return cached

    url = f"{CTGOV_BASE}/studies?{urlencode(params)}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            response.raise_for_status()
            data = await response.json()

    studies = data.get("studies", [])
    trials = [_parse_trial(s) for s in studies]

    _set_cached(key, trials)
    return trials
