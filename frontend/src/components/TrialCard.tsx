"use client";

import { useState } from "react";
import type { RankedTrial, CriterionResult } from "@/lib/types";

interface TrialCardProps {
  trial: RankedTrial;
}

function CriterionBadge({ result }: { result: CriterionResult }) {
  const colors = {
    met: "bg-green-50 text-green-700 border-green-200",
    failed: "bg-red-50 text-red-700 border-red-200",
    uncertain: "bg-amber-50 text-amber-700 border-amber-200",
  };
  const status = result.met === true ? "met" : result.met === false ? "failed" : "uncertain";
  const icon = result.met === true ? "+" : result.met === false ? "-" : "?";

  return (
    <div className={`rounded-md border px-3 py-2 text-xs ${colors[status]}`}>
      <div className="flex items-start gap-2">
        <span className="font-bold flex-shrink-0">{icon}</span>
        <div>
          <p className="font-medium">{result.criterion_text}</p>
          <p className="mt-0.5 opacity-80">{result.reasoning}</p>
        </div>
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 0.7 ? "text-green-700 bg-green-50" : score >= 0.4 ? "text-amber-700 bg-amber-50" : "text-red-700 bg-red-50";
  return (
    <span className={`text-sm font-semibold px-2.5 py-1 rounded-full ${color}`}>
      {(score * 100).toFixed(0)}%
    </span>
  );
}

function EligibilityBadge({ eligible }: { eligible: string }) {
  const styles: Record<string, string> = {
    yes: "bg-green-100 text-green-800",
    no: "bg-red-100 text-red-800",
    maybe: "bg-amber-100 text-amber-800",
  };
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded ${styles[eligible] ?? styles.maybe}`}>
      {eligible === "yes" ? "Eligible" : eligible === "no" ? "Ineligible" : "Possibly Eligible"}
    </span>
  );
}

export default function TrialCard({ trial }: TrialCardProps) {
  const [expanded, setExpanded] = useState(false);
  const { evaluation } = trial;

  return (
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden hover:shadow-md transition-shadow">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-gray-400">#{trial.rank}</span>
              <EligibilityBadge eligible={evaluation.eligible} />
              <span className="text-xs text-gray-400">{evaluation.nct_id}</span>
            </div>
            <h3 className="text-sm font-semibold text-gray-900 leading-snug">{trial.title}</h3>
          </div>
          <ScoreBadge score={trial.score} />
        </div>

        <p className="mt-2 text-sm text-gray-600 leading-relaxed">{trial.match_summary}</p>

        <div className="mt-3 flex items-center gap-4 text-xs text-gray-500">
          <span className="flex items-center gap-1">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-400" />
            {evaluation.criteria_met.length} met
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-400" />
            {evaluation.criteria_failed.length} failed
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-400" />
            {evaluation.criteria_uncertain.length} uncertain
          </span>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-5 py-2.5 text-xs font-medium text-gray-500 bg-gray-50 hover:bg-gray-100 border-t border-gray-100 transition-colors flex items-center justify-center gap-1"
      >
        {expanded ? "Hide" : "Show"} criteria details
        <svg className={`h-3 w-3 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {expanded && (
        <div className="px-5 py-4 border-t border-gray-100 space-y-2 bg-gray-50/50">
          {evaluation.criteria_met.map((c, i) => (
            <CriterionBadge key={`met-${i}`} result={c} />
          ))}
          {evaluation.criteria_failed.map((c, i) => (
            <CriterionBadge key={`fail-${i}`} result={c} />
          ))}
          {evaluation.criteria_uncertain.map((c, i) => (
            <CriterionBadge key={`unc-${i}`} result={c} />
          ))}
          {evaluation.reasoning && (
            <p className="text-xs text-gray-500 pt-2 border-t border-gray-200 italic">
              {evaluation.reasoning}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
