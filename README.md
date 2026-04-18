# Clinical Trial Matcher

A multi-agent system built with **LangGraph** that matches patients to recruiting clinical trials. Given a free-text patient description, the system extracts structured clinical data, searches [ClinicalTrials.gov](https://clinicaltrials.gov), evaluates eligibility criteria, and returns ranked matches with plain-language explanations.

> **Note:** All patient data used in this project is synthetic. No real PHI is stored or processed.

---

## Why This Exists

Matching patients to clinical trials is slow, manual, and error-prone. Coordinators sift through hundreds of trials, cross-referencing eligibility criteria against patient records — a process that can take hours per patient. This project automates that workflow using a pipeline of specialized AI agents, each handling a distinct step in the matching process.

This is a production-grade evolution of a patient matching system built during a pharma consulting engagement — an LLM-powered trial matching agent using RAG and vector embeddings across 50+ clinical programs. This project applies those learnings on LangGraph with full observability, evaluation, and deployment.

---

## How It Works

```
Patient Description (free text)
        │
        ▼
┌──────────────┐     ┌──────────────┐     ┌───────────────────┐
│   Intake     │────▶│   Search     │────▶│   Eligibility     │
│   Agent      │     │   Agent      │     │   Evaluator       │
│              │     │              │     │                   │
│ Extracts     │     │ Queries      │     │ Evaluates each    │
│ structured   │     │ CT.gov API   │     │ criterion per     │
│ patient      │     │ for recruiting│    │ trial in parallel │
│ profile      │     │ trials       │     │                   │
└──────┬───────┘     └──────────────┘     └────────┬──────────┘
       │                                           │
       │  ┌──────────────┐     ┌──────────────┐    │
       │  │   Human      │◀────│   Ranker     │◀───┘
       └─▶│   Review     │     │   Agent      │
          │              │     │              │
          │ Pauses for   │     │ Scores,      │
          │ clarification│     │ ranks, and   │
          │ via interrupt│     │ summarizes   │
          └──────────────┘     └──────────────┘
```

### The Five Agents

| Agent | Model | Role |
|-------|-------|------|
| **Intake Agent** | Claude Haiku 4.5 | Extracts a structured `PatientProfile` from free-text input using structured output. Validates required fields (age, diagnosis). Routes to human review if critical data is missing. |
| **Search Agent** | None (deterministic) | Queries the ClinicalTrials.gov API v2 for recruiting trials matching the patient's condition, stage, and location. Results are cached with a 24-hour TTL. |
| **Eligibility Evaluator** | Claude Sonnet 4.6 | The most expensive node. Evaluates the patient against every inclusion/exclusion criterion for each trial, running evaluations in parallel via `asyncio.gather()`. Marks ambiguous criteria as "uncertain" rather than guessing. |
| **Ranker Agent** | Claude Sonnet 4.6 | Filters out ineligible trials, scores the rest using a weighted formula (criteria match ratio, trial phase, recency), and generates a plain-language match summary for each. |
| **Human Review** | None (interrupt) | Pauses execution when clarification is needed — either missing patient data or too many uncertain eligibility criteria. Uses LangGraph's `interrupt()` + `Command(goto=...)` for dynamic re-entry to whichever node requested clarification. |

### Scoring Formula

```
score = 0.6 × criteria_met_ratio + 0.3 × phase_score + 0.1 × recency_score
```

- **Criteria met ratio**: Proportion of eligibility criteria the patient satisfies
- **Phase score**: Phase 3 (1.0) > Phase 2 (0.7) > Phase 1 (0.4)
- **Recency score**: Decays linearly over 365 days from last trial update

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Agent Orchestration | LangGraph (StateGraph) |
| LLM — Extraction | Claude Haiku 4.5 (structured output, low cost) |
| LLM — Reasoning | Claude Sonnet 4.6 (eligibility evaluation, ranking) |
| Data Source | [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/about-api) |
| Persistence | MemorySaver (dev) / PostgresSaver (prod) |
| Observability | LangSmith (tracing, dashboards) |
| Language | Python 3.11+ |

### Key Packages

```
langgraph >= 0.4
langchain >= 0.3
langchain-anthropic >= 0.3
langsmith >= 0.3
httpx >= 0.27
pydantic >= 2.0
```

---

## Data Models

The system operates on a well-defined set of Pydantic models:

```python
class PatientProfile:
    age: int
    sex: str
    diagnosis: str
    stage: str | None
    prior_therapies: list[str]
    biomarkers: list[str]           # e.g. ["HER2+", "EGFR+"]
    performance_status: str | None  # e.g. "ECOG 1"
    comorbidities: list[str]
    location: str | None

class TrialEvaluation:
    nct_id: str
    criteria_met: list[CriterionResult]
    criteria_failed: list[CriterionResult]
    criteria_uncertain: list[CriterionResult]
    eligible: str  # "yes" | "no" | "maybe"
    reasoning: str

class RankedTrial:
    nct_id: str
    title: str
    rank: int
    score: float
    match_summary: str  # plain-language explanation
    evaluation: TrialEvaluation
```

---

## Project Structure

```
clin_matcher/
  langgraph.json              # LangGraph Platform configuration
  pyproject.toml              # Dependencies and project metadata
  src/
    __main__.py               # CLI entry point
    graph/
      state.py                # Data models + TrialMatchState
      graph.py                # StateGraph definition, edges, routing
      nodes/
        intake.py             # Patient profile extraction
        search.py             # ClinicalTrials.gov API queries
        eligibility.py        # Per-criterion eligibility evaluation
        ranker.py             # Scoring, ranking, summary generation
        human_review.py       # interrupt() + Command(goto=...)
    prompts/
      intake.py               # Extraction prompt templates
      eligibility.py          # Criterion evaluation prompts
      ranker.py               # Match summary prompts
    tools/
      clinical_trials_api.py  # CT.gov v2 async client with caching
    eval/                     # Evaluation datasets and evaluators
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
git clone https://github.com/garciar8-port/clin_matcher.git
cd clin_matcher

python -m venv .venv
source .venv/bin/activate
pip install -e .

cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Run

```bash
python -m src "62-year-old female, stage IV HER2+ breast cancer, prior trastuzumab and pertuzumab, liver mets, ECOG 0"
```

Example output:

```
============================================================
Clinical Trial Matcher
============================================================

Input: 62-year-old female, stage IV HER2+ breast cancer...

[intake_agent] completed
  Patient: 62yo female, breast cancer
  Biomarkers: HER2+
[search_agent] completed
  Found 18 candidate trials
[eligibility_evaluator] completed
  Evaluated 18 trials, 7 potentially eligible
[ranker_agent] completed

============================================================
RANKED MATCHES
============================================================

  #1 [0.82] T-DXd vs TPC in HER2+ Metastatic Breast Cancer
     NCT: NCT04538742
     Strong match — patient meets all major inclusion criteria including
     HER2+ status, prior anti-HER2 therapy, and adequate performance
     status. Liver metastases are permitted.

  #2 [0.71] Tucatinib + Capecitabine in Advanced HER2+ BC
     NCT: NCT05514054
     ...

Disclaimer: This is not medical advice. Verify with a healthcare provider.
```

---

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Separate extraction and reasoning models** | Haiku handles structured extraction at low cost; Sonnet handles complex multi-criteria reasoning where accuracy matters |
| **Parallel eligibility evaluation** | Each trial is evaluated independently — `asyncio.gather()` cuts latency proportionally to trial count |
| **Three-valued eligibility (met/not met/uncertain)** | "Uncertain" prevents hallucinated verdicts on ambiguous criteria and triggers human review when needed |
| **`interrupt()` + `Command(goto=...)`** | Dynamic re-entry routing lets any node request clarification without hardcoding return edges |
| **24-hour trial cache** | ClinicalTrials.gov data changes infrequently; caching reduces API calls and latency |
| **Weighted scoring over pure LLM ranking** | Deterministic scoring is auditable and debuggable; LLM generates summaries, not scores |

---

## Roadmap

- [x] Core graph with all 5 agents
- [x] ClinicalTrials.gov API v2 integration
- [x] Human-in-the-loop with interrupt/resume
- [x] CLI entry point
- [ ] LangSmith tracing and dashboards
- [ ] PostgresSaver for persistent checkpointing
- [ ] Streaming output (SSE with `updates` + `messages` modes)
- [ ] Next.js frontend
- [ ] Evaluation suite (50 synthetic cases)
- [ ] CI pipeline with eval gating
- [ ] LangGraph Platform deployment

---

## Disclaimer

This tool is for research and demonstration purposes only. It is **not medical advice**. All trial matching results should be verified by a qualified healthcare provider. All patient data used in development and testing is entirely synthetic.

---

## License

MIT
