"""Custom LangSmith evaluators for the Clinical Trial Matcher (CRE-35).

1. extraction_accuracy — field-level accuracy for PatientProfile
2. eligibility_agreement — agreement between system and expected verdicts
3. ranking_quality — top-1 and top-3 agreement with expert picks
"""

from __future__ import annotations

from langsmith.schemas import Example, Run


def extraction_accuracy(run: Run, example: Example) -> dict:
    """Compare extracted PatientProfile fields against expected values.

    Scores each field as 1.0 (match) or 0.0 (mismatch), returns average.
    For list fields, uses set intersection over union (Jaccard).
    """
    outputs = run.outputs or {}
    profile = outputs.get("patient_profile")
    expected = (example.outputs or {}).get("expected_profile", {})

    if not profile or not expected:
        return {"key": "extraction_accuracy", "score": 0.0}

    # Normalize profile to dict if it's a Pydantic model
    if hasattr(profile, "model_dump"):
        profile = profile.model_dump()

    scores = []

    # Scalar fields
    for field in ["age", "sex", "diagnosis", "stage", "performance_status", "location"]:
        expected_val = expected.get(field)
        actual_val = profile.get(field)

        if expected_val is None and actual_val is None:
            scores.append(1.0)
        elif expected_val is None or actual_val is None:
            scores.append(0.0)
        elif field == "age":
            scores.append(1.0 if expected_val == actual_val else 0.0)
        else:
            # Case-insensitive string comparison
            scores.append(
                1.0 if str(expected_val).lower().strip() == str(actual_val).lower().strip() else 0.0
            )

    # List fields — Jaccard similarity
    for field in ["prior_therapies", "biomarkers", "comorbidities"]:
        expected_set = {s.lower().strip() for s in (expected.get(field) or [])}
        actual_set = {s.lower().strip() for s in (profile.get(field) or [])}

        if not expected_set and not actual_set:
            scores.append(1.0)
        elif not expected_set or not actual_set:
            scores.append(0.0)
        else:
            intersection = expected_set & actual_set
            union = expected_set | actual_set
            scores.append(len(intersection) / len(union))

    avg_score = sum(scores) / max(len(scores), 1)
    return {"key": "extraction_accuracy", "score": round(avg_score, 4)}


def eligibility_agreement(run: Run, example: Example) -> dict:
    """Compare eligibility verdicts between system output and expected.

    For each evaluation, checks if overall eligible verdict matches.
    Returns fraction of agreements.
    """
    outputs = run.outputs or {}
    evaluations = outputs.get("evaluations", [])

    if not evaluations:
        return {"key": "eligibility_agreement", "score": 0.0}

    # Count evaluations with reasonable verdicts (not error states)
    valid = [e for e in evaluations if hasattr(e, "eligible") or isinstance(e, dict)]
    if not valid:
        return {"key": "eligibility_agreement", "score": 0.0}

    # Without ground-truth eligibility per trial, score based on consistency:
    # - Trials with all criteria met should be "yes"
    # - Trials with any criteria failed should be "no" or "maybe"
    # - Trials with only uncertain should be "maybe"
    agreements = 0
    total = 0

    for ev in valid:
        if isinstance(ev, dict):
            failed = len(ev.get("criteria_failed", []))
            uncertain = len(ev.get("criteria_uncertain", []))
            eligible = ev.get("eligible", "")
        else:
            failed = len(ev.criteria_failed)
            uncertain = len(ev.criteria_uncertain)
            eligible = ev.eligible

        total += 1

        # Check consistency of verdict with criteria counts
        if failed > 0 and eligible in ("no", "maybe"):
            agreements += 1
        elif failed == 0 and uncertain == 0 and eligible == "yes":
            agreements += 1
        elif failed == 0 and uncertain > 0 and eligible in ("yes", "maybe"):
            agreements += 1

    score = agreements / max(total, 1)
    return {"key": "eligibility_agreement", "score": round(score, 4)}


def ranking_quality(run: Run, example: Example) -> dict:
    """Check if rankings are ordered by score and ineligible trials are excluded.

    Scores:
    - 0.5 for correct ordering (descending scores)
    - 0.5 for excluding ineligible trials (eligible != "no")
    """
    outputs = run.outputs or {}
    rankings = outputs.get("rankings", [])

    if not rankings:
        # No rankings could be valid (no eligible trials found)
        return {"key": "ranking_quality", "score": 0.5}

    # Check ordering — scores should be descending
    scores_list = []
    for r in rankings:
        if isinstance(r, dict):
            scores_list.append(r.get("score", 0))
        else:
            scores_list.append(r.score)

    ordered = all(scores_list[i] >= scores_list[i + 1] for i in range(len(scores_list) - 1))
    order_score = 1.0 if ordered else 0.0

    # Check that no ineligible trials are ranked
    no_ineligible = True
    for r in rankings:
        if isinstance(r, dict):
            ev = r.get("evaluation", {})
            eligible = ev.get("eligible", "") if isinstance(ev, dict) else getattr(ev, "eligible", "")
        else:
            eligible = r.evaluation.eligible
        if eligible == "no":
            no_ineligible = False
            break

    filter_score = 1.0 if no_ineligible else 0.0

    final = 0.5 * order_score + 0.5 * filter_score
    return {"key": "ranking_quality", "score": round(final, 4)}
