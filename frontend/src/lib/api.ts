/** FastAPI backend client for thread and run management. */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8123";

export async function createThreadAndRun(
  patientText: string,
  onUpdate: (nodeName: string, data: Record<string, unknown>) => void,
  onComplete: () => void,
  onError: (error: string) => void,
) {
  try {
    // Create thread
    const threadRes = await fetch(`${API_URL}/threads`, { method: "POST" });
    if (!threadRes.ok) throw new Error("Failed to create thread");
    const { thread_id: threadId } = await threadRes.json();

    // Start run with SSE streaming
    const runRes = await fetch(`${API_URL}/threads/${threadId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: { raw_input: patientText } }),
    });

    if (!runRes.ok) throw new Error("Failed to start run");
    if (!runRes.body) throw new Error("No response body");

    await consumeSSE(runRes.body, onUpdate);
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
    const res = await fetch(`${API_URL}/threads/${threadId}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ responses }),
    });

    if (!res.ok) throw new Error("Failed to resume thread");
    if (!res.body) throw new Error("No response body");

    await consumeSSE(res.body, onUpdate);
    onComplete();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    onError(message);
  }
}

async function consumeSSE(
  body: ReadableStream<Uint8Array>,
  onUpdate: (nodeName: string, data: Record<string, unknown>) => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let currentEvent = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("event:")) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith("data:") && currentEvent === "updates") {
        try {
          const data = JSON.parse(line.slice(5).trim());
          for (const [nodeName, update] of Object.entries(data)) {
            onUpdate(nodeName, update as Record<string, unknown>);
          }
        } catch {
          // Skip malformed JSON
        }
      }
    }
  }
}
