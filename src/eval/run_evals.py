"""LangSmith evaluation runner with custom evaluators (CRE-35).

Three evaluators:
1. Extraction accuracy — field-level accuracy for PatientProfile (target >95%)
2. Eligibility agreement — LLM-as-judge comparing verdicts (target >85%)
3. Ranking quality — top-1 and top-3 agreement with expert picks (target >70%)

Usage:
    python -m src.eval.run_evals                    # run all evaluators
    python -m src.eval.run_evals --evaluator extraction  # run one evaluator
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langsmith import Client
from langsmith.evaluation import evaluate

from src.eval.evaluators import (
    extraction_accuracy,
    eligibility_agreement,
    ranking_quality,
)

DATASET_PATH = Path(__file__).parent / "datasets" / "eval_cases.json"
DATASET_NAME = "clinical-trial-matcher-eval-v1"

# Score thresholds from docs/targets.md
THRESHOLDS = {
    "extraction_accuracy": 0.95,
    "eligibility_agreement": 0.85,
    "ranking_quality": 0.70,
}


def load_dataset() -> list[dict]:
    with open(DATASET_PATH) as f:
        return json.load(f)


def ensure_dataset(client: Client) -> None:
    """Upload or update the LangSmith dataset."""
    cases = load_dataset()

    existing = list(client.list_datasets(dataset_name=DATASET_NAME))
    if existing:
        dataset = existing[0]
        print(f"Using existing dataset: {DATASET_NAME} ({dataset.id})")
    else:
        dataset = client.create_dataset(
            dataset_name=DATASET_NAME,
            description="50-case synthetic evaluation dataset for Clinical Trial Matcher",
        )
        print(f"Created dataset: {DATASET_NAME} ({dataset.id})")

        for case in cases:
            client.create_example(
                dataset_id=dataset.id,
                inputs={"raw_input": case["input"]},
                outputs={
                    "expected_profile": case["expected_profile"],
                    "difficulty": case["difficulty"],
                    "id": case["id"],
                },
            )
        print(f"Uploaded {len(cases)} examples")


def target(inputs: dict) -> dict:
    """Run the graph on a single input and return outputs for evaluation."""
    import asyncio
    from src.graph.graph import graph

    async def _run():
        config = {"configurable": {"thread_id": f"eval-{inputs.get('id', 'unknown')}"}}
        state = {
            "raw_input": inputs["raw_input"],
            "candidate_trials": [],
            "evaluations": [],
            "rankings": [],
            "clarifications_needed": [],
            "clarifications_received": [],
            "current_node": "",
            "error_log": [],
            "metadata": {},
        }

        final = {}
        async for event in graph.astream(state, config, stream_mode="updates"):
            for node_name, update in event.items():
                final.update(update)

        return final

    return asyncio.run(_run())


def run_extraction_eval(client: Client) -> float:
    """Run extraction accuracy evaluation."""
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[extraction_accuracy],
        experiment_prefix="extraction-accuracy",
        max_concurrency=4,
    )
    scores = [r.get("results", {}).get("extraction_accuracy", {}).get("score", 0) for r in results]
    avg = sum(scores) / max(len(scores), 1)
    print(f"Extraction accuracy: {avg:.3f} (threshold: {THRESHOLDS['extraction_accuracy']})")
    return avg


def run_eligibility_eval(client: Client) -> float:
    """Run eligibility agreement evaluation."""
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[eligibility_agreement],
        experiment_prefix="eligibility-agreement",
        max_concurrency=2,
    )
    scores = [r.get("results", {}).get("eligibility_agreement", {}).get("score", 0) for r in results]
    avg = sum(scores) / max(len(scores), 1)
    print(f"Eligibility agreement: {avg:.3f} (threshold: {THRESHOLDS['eligibility_agreement']})")
    return avg


def run_ranking_eval(client: Client) -> float:
    """Run ranking quality evaluation."""
    results = evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[ranking_quality],
        experiment_prefix="ranking-quality",
        max_concurrency=2,
    )
    scores = [r.get("results", {}).get("ranking_quality", {}).get("score", 0) for r in results]
    avg = sum(scores) / max(len(scores), 1)
    print(f"Ranking quality: {avg:.3f} (threshold: {THRESHOLDS['ranking_quality']})")
    return avg


def main():
    parser = argparse.ArgumentParser(description="Run LangSmith evaluations")
    parser.add_argument(
        "--evaluator",
        choices=["extraction", "eligibility", "ranking", "all"],
        default="all",
    )
    parser.add_argument("--upload-only", action="store_true", help="Only upload dataset")
    args = parser.parse_args()

    client = Client()
    ensure_dataset(client)

    if args.upload_only:
        return

    results = {}
    if args.evaluator in ("extraction", "all"):
        results["extraction_accuracy"] = run_extraction_eval(client)
    if args.evaluator in ("eligibility", "all"):
        results["eligibility_agreement"] = run_eligibility_eval(client)
    if args.evaluator in ("ranking", "all"):
        results["ranking_quality"] = run_ranking_eval(client)

    # Check thresholds
    print(f"\n{'='*50}")
    all_passed = True
    for name, score in results.items():
        threshold = THRESHOLDS[name]
        passed = score >= threshold
        status = "PASS" if passed else "FAIL"
        print(f"  {status}: {name} = {score:.3f} (>= {threshold})")
        if not passed:
            all_passed = False

    if not all_passed:
        print("\nEvaluation FAILED — scores below threshold")
        sys.exit(1)
    else:
        print("\nAll evaluations PASSED")


if __name__ == "__main__":
    main()
