# Service-Level Objectives (SLOs)

Performance and quality targets for the Clinical Trial Matcher. These anchor the evaluation suite (Phase 4) and CI gating thresholds.

## Quality Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Extraction accuracy | >= 95% | Field-level accuracy on 50-case eval dataset |
| Eligibility agreement | >= 85% | LLM-as-judge vs expert annotations |
| Ranking quality (top-1) | >= 70% | Agreement with expert top pick |
| Ranking quality (top-3) | >= 85% | Expert pick appears in top 3 |
| Uncertain rate | <= 20% | Criteria marked "uncertain" per evaluation |

## Latency Budget (p95)

| Stage | Budget |
|-------|--------|
| Intake (extraction) | < 2s |
| Search (CT.gov API) | < 5s |
| Eligibility (parallel, 20 trials) | < 15s |
| Ranker (scoring + summaries) | < 10s |
| **End-to-end** | **< 30s** |

## Cost Ceiling

| Metric | Ceiling |
|--------|---------|
| Cost per run (20 trials) | < $0.15 |
| Intake (Haiku) | < $0.005 |
| Eligibility (Sonnet x 20) | < $0.10 |
| Ranking summaries (Sonnet) | < $0.04 |

## Reliability

| Metric | Target |
|--------|--------|
| CT.gov API success rate | >= 99% (with retries) |
| Graph completion rate | >= 95% (no unhandled errors) |
| Human review trigger rate | 5-15% of runs |

## Notes

- Latency measured from `graph.astream()` start to final `rankings` output.
- Cost estimates based on Claude Haiku 4.5 ($0.80/1M input, $4/1M output) and Sonnet 4.6 ($3/1M input, $15/1M output) pricing.
- Quality targets are aspirational for Phase 4 eval suite — baselines will be established from the first eval run.
- Uncertain rate is a proxy for prompt quality — high uncertainty suggests prompts need refinement or patient descriptions lack detail.
