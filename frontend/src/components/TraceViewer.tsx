"use client";

import { useState } from "react";

export interface TraceEvent {
  node: string;
  timestamp: number;
  data: Record<string, unknown>;
}

interface TraceViewerProps {
  events: TraceEvent[];
}

const NODE_COLORS: Record<string, string> = {
  intake_agent: "bg-purple-500",
  search_agent: "bg-blue-500",
  eligibility_evaluator: "bg-amber-500",
  ranker_agent: "bg-green-500",
  human_review: "bg-red-500",
};

const NODE_LABELS: Record<string, string> = {
  intake_agent: "Intake Agent",
  search_agent: "Search Agent",
  eligibility_evaluator: "Eligibility Evaluator",
  ranker_agent: "Ranker Agent",
  human_review: "Human Review",
};

function formatDuration(startMs: number, endMs: number): string {
  const dur = endMs - startMs;
  if (dur < 1000) return `${dur}ms`;
  return `${(dur / 1000).toFixed(1)}s`;
}

function summarizeData(node: string, data: Record<string, unknown>): string[] {
  const lines: string[] = [];

  if (data.patient_profile) {
    const p = data.patient_profile as Record<string, unknown>;
    lines.push(`Patient: ${p.age}yo ${p.sex}, ${p.diagnosis}`);
    if (p.stage) lines.push(`Stage: ${p.stage}`);
    if (Array.isArray(p.biomarkers) && p.biomarkers.length) lines.push(`Biomarkers: ${p.biomarkers.join(", ")}`);
    if (Array.isArray(p.prior_therapies) && p.prior_therapies.length) lines.push(`Prior therapies: ${p.prior_therapies.join(", ")}`);
    if (p.performance_status) lines.push(`Performance: ${p.performance_status}`);
  }

  if (data.candidate_trials) {
    const trials = data.candidate_trials as unknown[];
    lines.push(`Found ${trials.length} candidate trials`);
    for (const t of trials.slice(0, 3)) {
      const trial = t as Record<string, unknown>;
      lines.push(`  ${trial.nct_id} — ${trial.title}`);
    }
    if (trials.length > 3) lines.push(`  ... and ${trials.length - 3} more`);
  }

  if (data.evaluations) {
    const evals = data.evaluations as Record<string, unknown>[];
    const eligible = evals.filter((e) => e.eligible !== "no").length;
    lines.push(`Evaluated ${evals.length} trials`);
    lines.push(`  ${eligible} eligible, ${evals.length - eligible} ineligible`);
    for (const ev of evals.slice(0, 3)) {
      const met = Array.isArray(ev.criteria_met) ? ev.criteria_met.length : 0;
      const failed = Array.isArray(ev.criteria_failed) ? ev.criteria_failed.length : 0;
      const unc = Array.isArray(ev.criteria_uncertain) ? ev.criteria_uncertain.length : 0;
      lines.push(`  ${ev.nct_id}: ${ev.eligible} (${met} met, ${failed} failed, ${unc} uncertain)`);
    }
    if (evals.length > 3) lines.push(`  ... and ${evals.length - 3} more`);
  }

  if (data.rankings) {
    const ranks = data.rankings as Record<string, unknown>[];
    lines.push(`Ranked ${ranks.length} trials`);
    for (const r of ranks) {
      lines.push(`  #${r.rank} [${((r.score as number) * 100).toFixed(0)}%] ${r.nct_id}`);
    }
  }

  if (data.clarifications_needed) {
    const cls = data.clarifications_needed as Record<string, unknown>[];
    if (cls.length > 0) {
      lines.push(`${cls.length} clarification(s) requested`);
      for (const c of cls) lines.push(`  Q: ${c.question}`);
    }
  }

  if (data.error_log) {
    const errs = data.error_log as string[];
    for (const e of errs) lines.push(`ERROR: ${e}`);
  }

  return lines;
}

export default function TraceViewer({ events }: TraceViewerProps) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);
  const startTime = events.length > 0 ? events[0].timestamp : 0;

  if (events.length === 0) {
    return (
      <div className="text-sm text-gray-400 text-center py-8">
        Run a query to see the execution trace.
      </div>
    );
  }

  return (
    <div className="space-y-1">
      {events.map((event, i) => {
        const color = NODE_COLORS[event.node] ?? "bg-gray-500";
        const label = NODE_LABELS[event.node] ?? event.node;
        const elapsed = `+${((event.timestamp - startTime) / 1000).toFixed(1)}s`;
        const duration =
          i < events.length - 1
            ? formatDuration(event.timestamp, events[i + 1].timestamp)
            : "—";
        const isExpanded = expandedIdx === i;
        const lines = summarizeData(event.node, event.data);

        return (
          <div key={i}>
            <button
              onClick={() => setExpandedIdx(isExpanded ? null : i)}
              className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-100 transition-colors text-left"
            >
              <div className={`h-3 w-3 rounded-full ${color} flex-shrink-0`} />
              <span className="text-sm font-medium text-gray-900 flex-1">{label}</span>
              <span className="text-xs font-mono text-gray-400">{elapsed}</span>
              <span className="text-xs font-mono text-gray-400 w-12 text-right">{duration}</span>
              <svg
                className={`h-3 w-3 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
              </svg>
            </button>

            {isExpanded && lines.length > 0 && (
              <div className="ml-9 mb-2 px-3 py-2 bg-gray-50 rounded-lg border border-gray-100">
                <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono leading-relaxed">
                  {lines.join("\n")}
                </pre>
              </div>
            )}

            {i < events.length - 1 && (
              <div className="ml-[21px] h-4 border-l-2 border-gray-200" />
            )}
          </div>
        );
      })}

      <div className="flex items-center gap-3 px-3 pt-2">
        <div className="h-3 w-3 rounded-full bg-gray-200 flex-shrink-0" />
        <span className="text-xs text-gray-400">
          Total: {((events[events.length - 1].timestamp - startTime) / 1000).toFixed(1)}s
        </span>
      </div>
    </div>
  );
}
