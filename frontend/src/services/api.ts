import axios from "axios";
import type {
  ChatRequest,
  ChatResponse,
  ChatStreamDoneEvent,
  ChatStreamEvent,
  ChatTurn,
  ChecklistRequest,
  ChecklistResponse,
  FeedbackRequest,
  FeedbackResponse,
  HealthResponse,
  SourceListResponse,
} from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await client.get<HealthResponse>("/health");
  return data;
}

export async function sendChatMessage(question: string): Promise<ChatResponse> {
  const payload: ChatRequest = { question };
  const { data } = await client.post<ChatResponse>("/api/chat", payload);
  return data;
}

export interface StreamChatCallbacks {
  onDelta: (text: string) => void;
  onDone: (event: ChatStreamDoneEvent) => void;
  onError: (detail: string) => void;
}

// Raw fetch + manual SSE parsing rather than axios: axios buffers the whole
// response before resolving, which defeats streaming. The backend sends
// "data: <json>\n\n" frames (see app/api/chat.py::_sse); a frame can arrive
// split across multiple reader chunks, so we buffer and split on the blank
// line that terminates each frame rather than assuming one chunk = one frame.
export async function streamChatMessage(
  question: string,
  history: ChatTurn[],
  callbacks: StreamChatCallbacks,
): Promise<void> {
  const payload: ChatRequest = { question, history };

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    callbacks.onError("Could not reach the backend. Please make sure the API server is running.");
    return;
  }

  if (!response.ok || !response.body) {
    callbacks.onError(`Request failed with status ${response.status}.`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const rawFrame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      const dataLine = rawFrame.split("\n").find((line) => line.startsWith("data: "));
      if (dataLine) {
        const event = JSON.parse(dataLine.slice(6)) as ChatStreamEvent;
        if (event.type === "delta") {
          callbacks.onDelta(event.text);
        } else if (event.type === "done") {
          callbacks.onDone(event);
        } else if (event.type === "error") {
          callbacks.onError(event.detail);
        }
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}

export async function getSources(category?: string): Promise<SourceListResponse> {
  const { data } = await client.get<SourceListResponse>("/api/sources", {
    params: category ? { category } : undefined,
  });
  return data;
}

export async function generateChecklist(
  request: ChecklistRequest,
): Promise<ChecklistResponse> {
  const { data } = await client.post<ChecklistResponse>(
    "/api/checklist/generate",
    request,
  );
  return data;
}

export async function submitFeedback(
  request: FeedbackRequest,
): Promise<FeedbackResponse> {
  const { data } = await client.post<FeedbackResponse>("/api/feedback", request);
  return data;
}
