import { getApiBaseUrl } from "@/services/api";
import type { ChatApiResponse } from "@/types/chat";
import type { SessionCreateRequest, SessionResponse } from "@/types/session";

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function createSession(payload: SessionCreateRequest): Promise<SessionResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new ApiError("Could not start a new session.", response.status);
  }

  return response.json();
}

export async function sendChatMessage(
  sessionId: string,
  message: string,
): Promise<ChatApiResponse> {
  const response = await fetch(`${getApiBaseUrl()}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });

  if (!response.ok) {
    throw new ApiError("Something went wrong sending your message.", response.status);
  }

  return response.json();
}
