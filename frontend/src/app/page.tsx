"use client";

import { useState, useCallback } from "react";
import PatientInput from "@/components/PatientInput";
import ProgressIndicator from "@/components/ProgressIndicator";
import TrialCard from "@/components/TrialCard";
import ClarificationForm from "@/components/ClarificationForm";
import TraceViewer, { type TraceEvent } from "@/components/TraceViewer";
import { createThreadAndRun, resumeThread } from "@/lib/api";
import type { AppState, RankedTrial, PatientProfile, Clarification, NodeUpdate } from "@/lib/types";

type Tab = "results" | "trace";

export default function Home() {
  const [state, setState] = useState<AppState>({ status: "idle" });
  const [completedNodes, setCompletedNodes] = useState<string[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("results");
  const [traceEvents, setTraceEvents] = useState<TraceEvent[]>([]);

  const handleUpdate = useCallback((nodeName: string, data: NodeUpdate) => {
    setCompletedNodes((prev) => [...prev, nodeName]);
    setTraceEvents((prev) => [...prev, { node: nodeName, timestamp: Date.now(), data: data as Record<string, unknown> }]);
    setState((prev) => {
      if (prev.status !== "running") return prev;
      return { ...prev, currentNode: nodeName };
    });

    if (data.clarifications_needed && data.clarifications_needed.length > 0) {
      setState({
        status: "clarification",
        clarifications: data.clarifications_needed as Clarification[],
        threadId: threadId ?? "",
      });
    }
  }, [threadId]);

  async function handleSubmit(patientText: string) {
    setCompletedNodes([]);
    setTraceEvents([]);
    setState({ status: "running", currentNode: "intake_agent", progress: [] });

    let profile: PatientProfile | null = null;
    let rankings: RankedTrial[] = [];
    let gotClarification = false;

    const id = await createThreadAndRun(
      patientText,
      (nodeName, data) => {
        handleUpdate(nodeName, data as NodeUpdate);
        if (data.patient_profile) profile = data.patient_profile as PatientProfile;
        if (data.rankings) rankings = data.rankings as RankedTrial[];
        if (data.clarifications_needed && (data.clarifications_needed as Clarification[]).length > 0) {
          gotClarification = true;
        }
      },
      () => {
        if (!gotClarification) {
          setState({ status: "complete", rankings, profile });
        }
      },
      (error) => {
        if (!gotClarification) {
          setState({ status: "error", message: error });
        }
      },
    );

    if (id) setThreadId(id);
  }

  async function handleClarification(responses: { question_id: string; answer: string }[]) {
    if (!threadId) return;

    setState({ status: "running", currentNode: "human_review", progress: [] });
    let rankings: RankedTrial[] = [];
    let profile: PatientProfile | null = null;
    let gotClarification = false;

    await resumeThread(
      threadId,
      responses,
      (nodeName, data) => {
        handleUpdate(nodeName, data as NodeUpdate);
        if (data.patient_profile) profile = data.patient_profile as PatientProfile;
        if (data.rankings) rankings = data.rankings as RankedTrial[];
        if (data.clarifications_needed && (data.clarifications_needed as Clarification[]).length > 0) {
          gotClarification = true;
        }
      },
      () => {
        if (!gotClarification) {
          setState({ status: "complete", rankings, profile });
        }
      },
      (error) => {
        if (!gotClarification) {
          setState({ status: "error", message: error });
        }
      },
    );
  }

  function handleReset() {
    setState({ status: "idle" });
    setCompletedNodes([]);
    setThreadId(null);
    setTraceEvents([]);
    setActiveTab("results");
  }

  const showTabs = state.status === "complete" || traceEvents.length > 0;

  return (
    <main className="mx-auto w-full max-w-6xl px-6 py-8 flex-1">
      {/* Input */}
      <section className="mb-8">
        <PatientInput
          onSubmit={handleSubmit}
          disabled={state.status === "running"}
        />
      </section>

      {/* Progress */}
      {state.status === "running" && (
        <section className="mb-8 rounded-xl border border-blue-100 bg-blue-50/50 p-5">
          <ProgressIndicator
            currentNode={state.currentNode}
            completedNodes={completedNodes}
          />
        </section>
      )}

      {/* Clarification */}
      {state.status === "clarification" && (
        <section className="mb-8">
          <ClarificationForm
            clarifications={state.clarifications}
            onSubmit={handleClarification}
            disabled={false}
          />
        </section>
      )}

      {/* Tabs */}
      {showTabs && state.status !== "running" && (
        <>
          <div className="flex gap-1 mb-4 border-b border-gray-200">
            <button
              onClick={() => setActiveTab("results")}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "results"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Results
            </button>
            <button
              onClick={() => setActiveTab("trace")}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                activeTab === "trace"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              Trace
            </button>
          </div>

          {/* Results Tab */}
          {activeTab === "results" && state.status === "complete" && (
            <section>
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-900">
                    {state.rankings.length > 0
                      ? `${state.rankings.length} Matching Trial${state.rankings.length !== 1 ? "s" : ""} Found`
                      : "No Matching Trials Found"}
                  </h2>
                  {state.profile && (
                    <p className="text-sm text-gray-500">
                      {state.profile.age}yo {state.profile.sex}, {state.profile.diagnosis}
                      {state.profile.stage ? ` stage ${state.profile.stage}` : ""}
                    </p>
                  )}
                </div>
                <button
                  onClick={handleReset}
                  className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  New Search
                </button>
              </div>

              <div className="space-y-4">
                {state.rankings.map((trial) => (
                  <TrialCard key={trial.nct_id} trial={trial} />
                ))}
              </div>

              <p className="mt-6 text-xs text-gray-400 text-center">
                This tool is for informational purposes only. Not medical advice. Always verify with a healthcare provider.
              </p>
            </section>
          )}

          {/* Trace Tab */}
          {activeTab === "trace" && (
            <section className="rounded-xl border border-gray-200 bg-white p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-semibold text-gray-900">Execution Trace</h2>
                {state.status === "complete" && (
                  <button
                    onClick={handleReset}
                    className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    New Search
                  </button>
                )}
              </div>
              <TraceViewer events={traceEvents} />
            </section>
          )}
        </>
      )}

      {/* Error */}
      {state.status === "error" && (
        <section className="rounded-xl border border-red-200 bg-red-50 p-5">
          <div className="flex items-start gap-3">
            <div className="h-8 w-8 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
              <svg className="h-4 w-4 text-red-600" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-red-900">Something went wrong</h3>
              <p className="text-sm text-red-700 mt-1">{state.message}</p>
              <button
                onClick={handleReset}
                className="mt-3 text-sm font-medium text-red-700 underline hover:text-red-800"
              >
                Try again
              </button>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
