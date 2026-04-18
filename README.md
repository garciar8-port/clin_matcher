# Clinical Trial Matcher

A production-grade multi-agent system built with **LangGraph** that matches patients to recruiting clinical trials. Given a free-text patient description, the system extracts structured clinical data, searches [ClinicalTrials.gov](https://clinicaltrials.gov), evaluates eligibility criteria in parallel, and returns ranked matches with plain-language explanations.

> **Note:** All patient data used in this project is synthetic. No real PHI is stored or processed.

---

## Architecture

```
Patient Description (free text)
        |
        v
+---------------+     +---------------+     +--------------------+
|   Intake      |---->|   Search      |---->|   Eligibility      |
|   Agent       |     |   Agent       |     |   Evaluator        |
|               |     |               |     |                    |
| Claude Haiku  |     | CT.gov API v2 |     | Claude Sonnet      |
| Extracts      |     | Fetches top   |     | Evaluates each     |
| PatientProfile|     | 20 recruiting |     | criterion per trial|
|               |     | trials        |     | via asyncio.gather |
+-------+-------+     +---------------+     +---------+----------+
        |                                              |
        |  +---------------+     +---------------+     |
        |  |   Human       |<----|   Ranker      |<----+
        +->|   Review      |     |   Agent       |
           |               |     |               |
           | interrupt()   |     | Claude Sonnet |
           | Pauses for    |     | Scores, ranks,|
           | clarification |     | summarizes    |
           +---------------+     +-------+-------+
                                         |
                                         v
                                  Ranked Trial Cards
                                  (Next.js Frontend)
```

### The Five Agents

| Agent | Model | Role |
|-------|-------|------|
| **Intake Agent** | Claude Haiku 4.5 | Extracts structured `PatientProfile` from free text. Validates required fields. Routes to human review if critical data is missing. |
| **Search Agent** | Deterministic | Queries ClinicalTrials.gov API v2 for recruiting trials matching condition, stage, and location. 24-hour TTL cache. |
| **Eligibility Evaluator** | Claude Sonnet 4.6 | Evaluates patient against every inclusion/exclusion criterion per trial in parallel. Three-valued logic: met / not met / uncertain. |
| **Ranker Agent** | Claude Sonnet 4.6 | Filters ineligible trials, scores with weighted formula, generates plain-language match summaries. |
| **Human Review** | Interrupt | Pauses via `interrupt()` + `Command(goto=...)` for dynamic re-entry when clarification is needed. |

### Scoring Formula

```
score = 0.6 x criteria_met_ratio + 0.3 x phase_score + 0.1 x recency_score
```

- **Criteria met ratio**: Proportion of eligibility criteria satisfied
- **Phase score**: Phase 3 (1.0) > Phase 2 (0.7) > Phase 1 (0.4)
- **Recency**: Linear decay over 365 days from last trial update

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 22+ (for frontend)
- [Anthropic API key](https://console.anthropic.com/)
- Docker (optional, for PostgresSaver)

### Backend

```bash
git clone https://github.com/garciar8-port/clin_matcher.git
cd clin_matcher

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Add your ANTHROPIC_API_KEY and LANGSMITH_API_KEY
```

**Run via CLI:**

```bash
python -m src "55-year-old male with stage III NSCLC, prior pembrolizumab, PD-L1 high, ECOG 1"
```

**Run with streaming:**

```bash
python -m src --stream "55-year-old male with stage III NSCLC, prior pembrolizumab"
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

### Docker (full stack)

```bash
docker compose up
# Backend: http://localhost:8123
# Frontend: cd frontend && npm run dev
```

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Agent Orchestration | LangGraph (StateGraph) |
| LLM — Extraction | Claude Haiku 4.5 |
| LLM — Reasoning | Claude Sonnet 4.6 |
| Data Source | ClinicalTrials.gov API v2 |
| Frontend | Next.js 16 + TypeScript + Tailwind |
| API Client | LangGraph SDK (SSE streaming) |
| Persistence | MemorySaver (dev) / PostgresSaver (prod) |
| Cross-session Memory | LangGraph Store |
| Retry / Resilience | Tenacity (exponential jitter) |
| Observability | LangSmith (tracing, evals) |
| CI | GitHub Actions (tests + eval gating) |
| Prompt Management | Versioned registry with LangSmith metadata |

---

## Testing

```bash
# Run all 62 unit + e2e tests (no API keys needed)
pytest tests/ -v

# Run evaluation suite (requires ANTHROPIC_API_KEY + LANGSMITH_API_KEY)
python -m src.eval.run_evals

# Run a single evaluator
python -m src.eval.run_evals --evaluator extraction
```

### Evaluation Suite

50 synthetic patient cases across 8 cancer types with gold-standard extraction profiles. Three custom LangSmith evaluators:

| Evaluator | What it measures | Target |
|-----------|-----------------|--------|
| Extraction accuracy | Field-level match for PatientProfile | >= 95% |
| Eligibility agreement | Verdict consistency with criteria counts | >= 85% |
| Ranking quality | Correct ordering + ineligible filtering | >= 70% |

---

## Project Structure

```
clin_matcher/
  langgraph.json                # LangGraph Platform config
  pyproject.toml                # Dependencies
  Dockerfile                    # Multi-stage production build
  docker-compose.yml            # Postgres + app
  src/
    __main__.py                 # CLI with multi-mode streaming
    graph/
      state.py                  # Pydantic data models + TrialMatchState
      graph.py                  # StateGraph, routing, checkpointer, store
      nodes/
        intake.py               # Profile extraction + Store persistence
        search.py               # CT.gov API with tenacity retry
        eligibility.py          # Parallel criterion evaluation
        ranker.py               # Scoring, ranking, summary generation
        human_review.py         # interrupt() + Command(goto=...)
    prompts/
      intake.py                 # Extraction prompts (v1.1)
      eligibility.py            # Criterion evaluation prompts (v1.1)
      ranker.py                 # Match summary prompts (v1.1)
      registry.py               # Versioned prompt registry
    tools/
      clinical_trials_api.py    # CT.gov v2 async client + 24hr cache
    utils/
      retry.py                  # Tenacity retry decorators
    eval/
      datasets/eval_cases.json  # 50-case synthetic dataset
      evaluators.py             # Custom LangSmith evaluators
      run_evals.py              # Evaluation runner with CI gating
  tests/                        # 62 unit + e2e tests
  docs/
    targets.md                  # SLO targets (quality, latency, cost)
  frontend/
    src/
      app/page.tsx              # Single-page app with state machine
      components/
        PatientInput.tsx         # Free-text input + example narratives
        ProgressIndicator.tsx    # 4-step pipeline progress
        TrialCard.tsx            # Ranked result cards with criteria details
        ClarificationForm.tsx    # Human-in-the-loop question UI
      lib/
        api.ts                  # LangGraph Platform SDK client
        types.ts                # TypeScript types matching Python models
```

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate extraction and reasoning models** | Haiku for structured extraction at low cost; Sonnet for complex multi-criteria reasoning |
| **Parallel eligibility evaluation** | `asyncio.gather()` across trials cuts latency proportionally |
| **Three-valued eligibility** | "Uncertain" prevents hallucinated verdicts, triggers human review |
| **`interrupt()` + `Command(goto=...)`** | Dynamic re-entry lets any node request clarification without hardcoded return edges |
| **Deterministic scoring** | Auditable weighted formula; LLM generates summaries not scores |
| **Tenacity retry with jitter** | Resilient to transient API failures (CT.gov + Claude) |
| **Prompt versioning registry** | Versions logged to LangSmith metadata for experiment tracking |
| **Conditional checkpointer** | MemorySaver in dev, PostgresSaver when DATABASE_URL is set |

---

## Disclaimer

This tool is for research and demonstration purposes only. It is **not medical advice**. All trial matching results should be verified by a qualified healthcare provider. All patient data is entirely synthetic.

---

## License

MIT
