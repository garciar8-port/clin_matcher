"""CLI entry point with multi-mode streaming: python -m src "patient description" """

from __future__ import annotations

import asyncio
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

from src.graph.graph import graph  # noqa: E402


NODE_LABELS = {
    "intake_agent": "Extracting patient profile",
    "search_agent": "Searching ClinicalTrials.gov",
    "eligibility_evaluator": "Evaluating eligibility",
    "ranker_agent": "Ranking matches",
    "human_review": "Awaiting clarification",
}


async def main(patient_text: str, stream_messages: bool = False) -> None:
    print(f"\n{'='*60}")
    print("Clinical Trial Matcher")
    print(f"{'='*60}\n")
    print(f"Input: {patient_text}\n")

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    initial_state = {
        "raw_input": patient_text,
        "candidate_trials": [],
        "evaluations": [],
        "rankings": [],
        "clarifications_needed": [],
        "clarifications_received": [],
        "current_node": "",
        "error_log": [],
        "metadata": {},
    }

    result = None

    if stream_messages:
        # Multi-mode streaming: updates (node progress) + messages (LLM tokens)
        async for stream_mode, chunk in graph.astream(
            initial_state,
            config,
            stream_mode=["updates", "messages"],
        ):
            if stream_mode == "updates":
                for node_name, update in chunk.items():
                    label = NODE_LABELS.get(node_name, node_name)
                    print(f"\n[{label}]")
                    _print_node_update(update)
                    if update.get("rankings"):
                        result = update["rankings"]

            elif stream_mode == "messages":
                # messages stream yields (AIMessageChunk, metadata)
                msg_chunk, metadata = chunk
                node = metadata.get("langgraph_node", "")
                if hasattr(msg_chunk, "content") and msg_chunk.content:
                    print(msg_chunk.content, end="", flush=True)
    else:
        # Updates-only mode (default)
        async for event in graph.astream(
            initial_state,
            config,
            stream_mode="updates",
        ):
            for node_name, update in event.items():
                label = NODE_LABELS.get(node_name, node_name)
                print(f"\n[{label}]")
                _print_node_update(update)
                if update.get("rankings"):
                    result = update["rankings"]

    _print_results(result)


def _print_node_update(update: dict) -> None:
    """Print relevant details from a node update."""
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

    if update.get("error_log"):
        for err in update["error_log"]:
            print(f"  ERROR: {err}")


def _print_results(rankings) -> None:
    """Print final ranked results."""
    if rankings:
        print(f"\n{'='*60}")
        print("RANKED MATCHES")
        print(f"{'='*60}\n")
        for trial in rankings:
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
        print("       python -m src --stream '<patient description>'")
        print('Example: python -m src "55yo male, stage III NSCLC, prior pembrolizumab, ECOG 1"')
        sys.exit(1)

    args = sys.argv[1:]
    stream = "--stream" in args
    if stream:
        args.remove("--stream")

    asyncio.run(main(" ".join(args), stream_messages=stream))
