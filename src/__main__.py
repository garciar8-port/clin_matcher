"""CLI entry point: python -m src "patient description" """

from __future__ import annotations

import asyncio
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

from src.graph.graph import graph


async def main(patient_text: str) -> None:
    print(f"\n{'='*60}")
    print("Clinical Trial Matcher")
    print(f"{'='*60}\n")
    print(f"Input: {patient_text}\n")

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = None
    async for event in graph.astream(
        {
            "raw_input": patient_text,
            "candidate_trials": [],
            "evaluations": [],
            "rankings": [],
            "clarifications_needed": [],
            "clarifications_received": [],
            "current_node": "",
            "error_log": [],
            "metadata": {},
        },
        config,
        stream_mode="updates",
    ):
        for node_name, update in event.items():
            current = update.get("current_node", node_name)
            print(f"[{current}] completed")

            if update.get("patient_profile"):
                profile = update["patient_profile"]
                print(f"  Patient: {profile.age}yo {profile.sex}, {profile.diagnosis}")
                if profile.biomarkers:
                    print(f"  Biomarkers: {', '.join(profile.biomarkers)}")

            if update.get("candidate_trials"):
                print(f"  Found {len(update['candidate_trials'])} candidate trials")

            if update.get("evaluations"):
                evals = update["evaluations"]
                eligible = sum(1 for e in evals if e.eligible != "no")
                print(f"  Evaluated {len(evals)} trials, {eligible} potentially eligible")

            if update.get("rankings"):
                result = update["rankings"]

            if update.get("error_log"):
                for err in update["error_log"]:
                    print(f"  ERROR: {err}")

    if result:
        print(f"\n{'='*60}")
        print("RANKED MATCHES")
        print(f"{'='*60}\n")
        for trial in result:
            print(f"  #{trial.rank} [{trial.score:.2f}] {trial.title}")
            print(f"     NCT: {trial.nct_id}")
            print(f"     {trial.match_summary}")
            print()
    else:
        print("\nNo matching trials found.")

    print("Disclaimer: This is not medical advice. Verify with a healthcare provider.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src '<patient description>'")
        print('Example: python -m src "55yo male, stage III NSCLC, prior pembrolizumab, ECOG 1"')
        sys.exit(1)

    asyncio.run(main(" ".join(sys.argv[1:])))
