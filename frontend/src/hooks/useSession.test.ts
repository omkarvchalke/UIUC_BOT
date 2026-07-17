import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as chatApi from "@/services/chatApi";
import type { SessionResponse } from "@/types/session";

import { useSession } from "./useSession";

function makeSessionResponse(overrides: Partial<SessionResponse> = {}): SessionResponse {
  return {
    id: "session-id",
    student_type: null,
    semester: null,
    college: null,
    department: null,
    created_at: "2026-01-01T00:00:00.000Z",
    updated_at: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("useSession", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts with no session until hydrated, then reports isReady", async () => {
    const { result } = renderHook(() => useSession());

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.sessionId).toBeNull();
    expect(result.current.studentType).toBeNull();
  });

  it("restores a previously persisted session from localStorage", async () => {
    localStorage.setItem("illiniguide.sessionId", "existing-session-id");
    localStorage.setItem("illiniguide.studentType", "graduate");

    const { result } = renderHook(() => useSession());

    await waitFor(() => expect(result.current.isReady).toBe(true));
    expect(result.current.sessionId).toBe("existing-session-id");
    expect(result.current.studentType).toBe("graduate");
  });

  it("starting a session persists the id and student type to localStorage", async () => {
    vi.spyOn(chatApi, "createSession").mockResolvedValue(
      makeSessionResponse({ id: "new-session-id", student_type: "freshman" }),
    );

    const { result } = renderHook(() => useSession());
    await waitFor(() => expect(result.current.isReady).toBe(true));

    await act(async () => {
      await result.current.startSession("freshman");
    });

    expect(result.current.sessionId).toBe("new-session-id");
    expect(result.current.studentType).toBe("freshman");
    expect(localStorage.getItem("illiniguide.sessionId")).toBe("new-session-id");
    expect(localStorage.getItem("illiniguide.studentType")).toBe("freshman");
  });

  it("skipping (null student type) does not write a studentType key", async () => {
    vi.spyOn(chatApi, "createSession").mockResolvedValue(
      makeSessionResponse({ id: "skip-session-id" }),
    );

    const { result } = renderHook(() => useSession());
    await waitFor(() => expect(result.current.isReady).toBe(true));

    await act(async () => {
      await result.current.startSession(null);
    });

    expect(result.current.sessionId).toBe("skip-session-id");
    expect(localStorage.getItem("illiniguide.studentType")).toBeNull();
  });

  it("surfaces an error message when session creation fails", async () => {
    vi.spyOn(chatApi, "createSession").mockRejectedValue(new Error("network down"));

    const { result } = renderHook(() => useSession());
    await waitFor(() => expect(result.current.isReady).toBe(true));

    await act(async () => {
      await result.current.startSession("transfer");
    });

    expect(result.current.error).toBe("network down");
    expect(result.current.sessionId).toBeNull();
  });

  it("retry re-attempts startSession with the last-tried student type", async () => {
    vi.spyOn(chatApi, "createSession")
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(makeSessionResponse({ id: "retry-session-id", student_type: "graduate" }));

    const { result } = renderHook(() => useSession());
    await waitFor(() => expect(result.current.isReady).toBe(true));

    await act(async () => {
      await result.current.startSession("graduate");
    });
    expect(result.current.error).toBe("network down");

    await act(async () => {
      await result.current.retry();
    });

    expect(chatApi.createSession).toHaveBeenLastCalledWith({ student_type: "graduate" });
    expect(result.current.sessionId).toBe("retry-session-id");
    expect(result.current.error).toBeNull();
  });

  it("resetSession clears both state and localStorage", async () => {
    localStorage.setItem("illiniguide.sessionId", "existing-session-id");
    localStorage.setItem("illiniguide.studentType", "graduate");

    const { result } = renderHook(() => useSession());
    await waitFor(() => expect(result.current.isReady).toBe(true));

    act(() => {
      result.current.resetSession();
    });

    expect(result.current.sessionId).toBeNull();
    expect(result.current.studentType).toBeNull();
    expect(localStorage.getItem("illiniguide.sessionId")).toBeNull();
    expect(localStorage.getItem("illiniguide.studentType")).toBeNull();
  });
});
