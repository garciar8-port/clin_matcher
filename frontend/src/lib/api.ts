/** LangGraph Platform API client for thread and run management. */

import { Client } from "@langchain/langgraph-sdk";

const API_URL = process.env.NEXT_PUBLIC_LANGGRAPH_API_URL ?? "http://localhost:8123";

export const client = new Client({ apiUrl: API_URL });

export async function createThreadAndRun(
  patientText: string,
  onUpdate: (nodeName: string, data: Record<string, unknown>) => void,
  onComplete: () => void,
  onError: (error: string) => void,
) {
  try {
    const thread = await client.threads.create();
    const threadId = thread.thread_id;

    const stream = client.runs.stream(threadId, "trial_matcher", {
      input: {
        raw_input: patientText,
        candidate_trials: [],
        evaluations: [],
        rankings: [],
        clarifications_needed: [],
        clarifications_received: [],
        current_node: "",
        error_log: [],
        metadata: {},
      },
      streamMode: "updates",
    });

    for await (const event of stream) {
      if (event.event === "updates") {
        const data = event.data as Record<string, Record<string, unknown>>;
        for (const [nodeName, update] of Object.entries(data)) {
          onUpdate(nodeName, update);
        }
      }
    }

    onComplete();
    return threadId;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    onError(message);
    return null;
  }
}

export async function resumeThread(
  threadId: string,
  responses: { question_id: string; answer: string }[],
  onUpdate: (nodeName: string, data: Record<string, unknown>) => void,
  onComplete: () => void,
  onError: (error: string) => void,
) {
  try {
    const state = await client.threads.getState(threadId);
    const resumeValue = responses;

    const stream = client.runs.stream(threadId, "trial_matcher", {
      input: null,
      command: { resume: resumeValue },
      streamMode: "updates",
    });

    for await (const event of stream) {
      if (event.event === "updates") {
        const data = event.data as Record<string, Record<string, unknown>>;
        for (const [nodeName, update] of Object.entries(data)) {
          onUpdate(nodeName, update);
        }
      }
    }

    onComplete();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    onError(message);
  }
}
