# Clinical Trial Matcher

A production-grade multi-agent system built with **LangGraph** that matches patients to recruiting clinical trials. Given a free-text patient description, the system extracts structured clinical data, searches [ClinicalTrials.gov](https://clinicaltrials.gov), evaluates eligibility criteria in parallel, and returns ranked matches with plain-language explanations.

> **Note:** All patient data used in this project is synthetic. No real PHI is stored or processed.

---

## Architecture

```
Patient Description (free text)
        |
        v
+---------------+     +---------------+     +---------------+
|   Intake      |---->|   Search      |---->|  Pre-filter   |
|   Agent       |     |   Agent       |     |               |
|               |     |               |     | Deterministic |
| Configurable  |     | CT.gov API v2 |     | Age, sex,     |
| LLM (Groq)   |     | Fetches top   |     | study type,   |
| Extracts      |     | 20 recruiting |     | condition     |
| PatientProfile|     | trials        |     | checks        |
+-------+-------+     +---------------+     +-------+-------+
        |                                           |
        |                                           v
        |                                   +--------------------+
        |                                   |   Eligibility      |
        |                                   |   Evaluator        |
        |                                   |                    |
        |                                   | Configurable LLM   |
        |                                   | (Together/Llama)   |
        |                                   | Parallel eval with |
        |                                   | 30s timeout        |
        |                                   +---------+----------+
        |                                             |
        |  +---------------+     +---------------+    |
        |  |   Human       |<----|   Ranker      |<---+
        +->|   Review      |     |   Agent       |
           |               |     |               |
           | interrupt()   |     | Configurable  |
           | Pauses for    |     | LLM (Groq)   |
           | clarification |     | Scores, ranks,|
           +---------------+     | summarizes    |
                                 +-------+-------+
                                         |
                                         v
                                  Ranked Trial Cards
                                  (Next.js Frontend)
```

### The Pipeline

| Step | Model/Method | Role |
|------|-------------|------|
| **Intake Agent** | Configurable (default: Groq/Llama 3.3 70B) | Extracts structured `PatientProfile` from free text. Validates required fields. Routes to human review if critical data is missing. |
| **Search Agent** | Deterministic | Queries ClinicalTrials.gov API v2 for recruiting trials matching condition, stage, and location. 24-hour TTL cache. |
| **Pre-filter** | Deterministic | Drops trials using structured CT.gov fields: age range, sex, study type (drops BASIC_SCIENCE, HEALTH_SERVICES_RESEARCH), and condition keyword mismatch. Caps at 10 trials. |
| **Eligibility Evaluator** | Configurable (default: Together/Llama 3.3 70B) | Evaluates patient against every inclusion/exclusion criterion per trial in parallel. Three-valued logic: met / not met / uncertain. 30s per-trial timeout. |
| **Ranker Agent** | Configurable (default: Groq/Llama 3.3 70B) | Filters ineligible trials, scores with weighted formula, generates plain-language match summaries. Displays trial sponsor. |
| **Human Review** | Interrupt | Pauses via `interrupt()` + `Command(goto=...)` for dynamic re-entry when clarification is needed. |

### Multi-Model Support

Each pipeline node can use a different LLM provider, configured via environment variables:

```
INTAKE_MODEL_PROVIDER=groq          # anthropic | deepseek | groq | together
INTAKE_MODEL_ID=llama-3.3-70b-versatile
ELIGIBILITY_MODEL_PROVIDER=together
ELIGIBILITY_MODEL_ID=meta-llama/Llama-3.3-70B-Instruct-Turbo
RANKER_MODEL_PROVIDER=groq
RANKER_MODEL_ID=llama-3.3-70b-versatile
```

Falls back to Claude Haiku if not configured.

### Scoring Formula

```
score = 0.6 x criteria_met_ratio + 0.3 x phase_score + 0.1 x recency_score
```

- **Criteria met ratio**: Proportion of determined criteria satisfied (uncertain criteria excluded from denominator)
- **Phase score**: Phase 3 (1.0) > Phase 2 (0.7) > Phase 1 (0.4)
- **Recency**: Linear decay over 365 days from last trial update

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 22+ (for frontend)
- API keys for at least one LLM provider (Groq, Together, DeepSeek, or Anthropic)
- Docker (optional, for PostgresSaver)

### Backend

```bash
git clone https://github.com/garciar8-port/clin_matcher.git
cd clin_matcher

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# Add your API keys (GROQ_API_KEY, TOGETHER_API_KEY, etc.)
# Configure model selection per node (see Multi-Model Support above)
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
| LLM Providers | Groq, Together AI, DeepSeek, Anthropic (configurable per node) |
| Data Source | ClinicalTrials.gov API v2 |
| Frontend | Next.js 16 + TypeScript + Tailwind |
| API Server | FastAPI (SSE streaming) |
| Persistence | AsyncPostgresSaver + AsyncPostgresStore (Neon) |
| Retry / Resilience | Tenacity (exponential jitter) |
| Observability | LangSmith (tracing with model provider metadata) |
| CI | GitHub Actions (tests + eval gating) |
| Deployment | Google Cloud Run |

---

## Testing

```bash
# Run all 62 unit + e2e tests (no API keys needed)
pytest tests/ -v

# Run evaluation suite (requires LLM API key + LANGSMITH_API_KEY)
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
  pyproject.toml                # Dependencies
  Dockerfile                    # Multi-stage production build
  docker-compose.yml            # Postgres + app (local dev)
  src/
    models.py                   # Multi-model config (provider selection per node)
    server.py                   # FastAPI server (SSE streaming)
    __main__.py                 # CLI with multi-mode streaming
    graph/
      state.py                  # Pydantic data models + TrialMatchState
      graph.py                  # StateGraph, routing, conditional edges
      nodes/
        intake.py               # Profile extraction + Store persistence
        search.py               # CT.gov API with tenacity retry
        prefilter.py            # Deterministic trial screening (age, sex, study type)
        eligibility.py          # Parallel criterion evaluation with timeout
        ranker.py               # Scoring, ranking, summary generation
        human_review.py         # interrupt() + Command(goto=...)
    prompts/
      intake.py                 # Extraction prompts (v1.1)
      eligibility.py            # Criterion evaluation prompts (v1.1)
      ranker.py                 # Match summary prompts (v1.1)
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
    Dockerfile                  # Next.js standalone production build
    src/
      app/page.tsx              # Single-page app with state machine
      components/
        PatientInput.tsx         # Free-text input + example narratives
        ProgressIndicator.tsx    # 4-step pipeline progress
        TrialCard.tsx            # Ranked result cards with sponsor + CT.gov links
        ClarificationForm.tsx    # Human-in-the-loop question UI
        TraceViewer.tsx          # Execution trace viewer
        Header.tsx               # App header
      lib/
        api.ts                  # FastAPI backend client (SSE)
        types.ts                # TypeScript types matching Python models
```

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Multi-model support** | Configurable per node via env vars. Groq for fast single-call nodes, Together for parallel evaluation. Falls back to Claude Haiku. |
| **Deterministic pre-filter** | Uses structured CT.gov fields (age, sex, study type) to drop ineligible trials before LLM evaluation — instant, no cost. |
| **Uncertain criteria excluded from scoring** | Missing patient info doesn't penalize match score — only determined criteria count. |
| **Parallel eligibility with timeout** | `asyncio.gather()` with 30s per-trial timeout. Timed-out trials marked "maybe" instead of blocking. |
| **Three-valued eligibility** | "Uncertain" prevents hallucinated verdicts, triggers human review |
| **`interrupt()` + `Command(goto=...)`** | Dynamic re-entry lets any node request clarification without hardcoded return edges |
| **Deterministic scoring** | Auditable weighted formula; LLM generates summaries not scores |
| **Tenacity retry with jitter** | Resilient to transient API failures (CT.gov + LLM providers) |
| **AsyncPostgresStore** | Persistent cross-session memory via Neon Postgres, survives container restarts |
| **Cloud Run deployment** | Backend + frontend as separate services, secrets via GCloud Secret Manager |

---

## Disclaimer

This tool is for research and demonstration purposes only. It is **not medical advice**. All trial matching results should be verified by a qualified healthcare provider. All patient data is entirely synthetic.

---

## License

MIT
