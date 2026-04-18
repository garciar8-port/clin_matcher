"""FastAPI server wrapping the LangGraph trial matcher.

Provides REST + SSE endpoints for the frontend:
  POST /threads              — create a thread
  POST /threads/{id}/run     — start a run with SSE streaming
  POST /threads/{id}/resume  — resume after interrupt
  GET  /threads/{id}/state   — get current state
  GET  /ok                   — healthcheck
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.graph.graph import builder

# Compile graph with persistence for interrupt/resume
checkpointer = MemorySaver()
store = InMemoryStore()
graph = builder.compile(checkpointer=checkpointer, store=store)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Clinical Trial Matcher API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---


class RunRequest(BaseModel):
    input: dict


class ResumeRequest(BaseModel):
    responses: list[dict]


# --- Endpoints ---


@app.get("/ok")
async def healthcheck():
    return {"status": "ok"}


@app.post("/threads")
async def create_thread():
    thread_id = str(uuid.uuid4())
    return {"thread_id": thread_id}


@app.post("/threads/{thread_id}/run")
async def run_graph(thread_id: str, request: RunRequest):
    """Start a graph run and stream results via SSE."""
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "raw_input": request.input.get("raw_input", ""),
        "candidate_trials": [],
        "evaluations": [],
        "rankings": [],
        "clarifications_needed": [],
        "clarifications_received": [],
        "current_node": "",
        "error_log": [],
        "metadata": request.input.get("metadata", {}),
    }

    async def event_stream():
        try:
            async for event in graph.astream(initial_state, config, stream_mode="updates"):
                for node_name, update in event.items():
                    if not isinstance(update, dict):
                        continue
                    # Serialize Pydantic models in the update
                    serialized = _serialize_update(update)
                    yield {
                        "event": "updates",
                        "data": json.dumps({node_name: serialized}),
                    }
            yield {"event": "end", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_stream())


@app.post("/threads/{thread_id}/resume")
async def resume_graph(thread_id: str, request: ResumeRequest):
    """Resume a graph after interrupt with user responses."""
    config = {"configurable": {"thread_id": thread_id}}

    async def event_stream():
        try:
            async for event in graph.astream(
                None, config, stream_mode="updates",
                command={"resume": request.responses},
            ):
                for node_name, update in event.items():
                    if not isinstance(update, dict):
                        continue
                    serialized = _serialize_update(update)
                    yield {
                        "event": "updates",
                        "data": json.dumps({node_name: serialized}),
                    }
            yield {"event": "end", "data": "{}"}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_stream())


@app.get("/threads/{thread_id}/state")
async def get_state(thread_id: str):
    """Get current graph state for a thread."""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        state = await graph.aget_state(config)
        return {"values": _serialize_update(state.values), "next": list(state.next)}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


def _serialize_update(update: dict) -> dict:
    """Convert Pydantic models to dicts for JSON serialization."""
    result = {}
    for key, value in update.items():
        if hasattr(value, "model_dump"):
            result[key] = value.model_dump()
        elif isinstance(value, list):
            result[key] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in value
            ]
        else:
            result[key] = value
    return result
