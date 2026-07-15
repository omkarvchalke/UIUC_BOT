import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as chatApi from "@/services/chatApi";

import { useChat } from "./useChat";

describe("useChat", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("loads persisted history for the given session id on mount", async () => {
    localStorage.setItem(
      "illiniguide.history.session-1",
      JSON.stringify([
        { id: "1", role: "user", content: "hi", createdAt: "2026-01-01T00:00:00.000Z" },
      ]),
    );

    const { result } = renderHook(() => useChat("session-1"));

    await waitFor(() => expect(result.current.messages).toHaveLength(1));
    expect(result.current.messages[0].content).toBe("hi");
  });

  it("does nothing when sessionId is null", async () => {
    const { result } = renderHook(() => useChat(null));

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.messages).toHaveLength(0);
  });

  it("appends the user message immediately, then the assistant reply once the API resolves", async () => {
    vi.spyOn(chatApi, "sendChatMessage").mockResolvedValue({
      answer: "Here's the answer.",
      grounded: true,
      needs_clarification: false,
      citations: [],
    });

    const { result } = renderHook(() => useChat("session-2"));

    await act(async () => {
      await result.current.sendMessage("How do I apply for OPT?");
    });

    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "How do I apply for OPT?",
    });
    expect(result.current.messages[1]).toMatchObject({
      role: "assistant",
      content: "Here's the answer.",
      grounded: true,
    });
    expect(result.current.isSending).toBe(false);

    const stored = JSON.parse(localStorage.getItem("illiniguide.history.session-2") ?? "[]");
    expect(stored).toHaveLength(2);
  });

  it("ignores blank/whitespace-only messages", async () => {
    const sendSpy = vi.spyOn(chatApi, "sendChatMessage");
    const { result } = renderHook(() => useChat("session-3"));

    await act(async () => {
      await result.current.sendMessage("   ");
    });

    expect(sendSpy).not.toHaveBeenCalled();
    expect(result.current.messages).toHaveLength(0);
  });

  it("surfaces an error and keeps the user's message on API failure", async () => {
    vi.spyOn(chatApi, "sendChatMessage").mockRejectedValue(new Error("Backend unreachable"));

    const { result } = renderHook(() => useChat("session-4"));

    await act(async () => {
      await result.current.sendMessage("hello");
    });

    expect(result.current.error).toBe("Backend unreachable");
    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0].role).toBe("user");
  });

  it("clearHistory empties messages and removes the localStorage entry", async () => {
    vi.spyOn(chatApi, "sendChatMessage").mockResolvedValue({
      answer: "ok",
      grounded: true,
      needs_clarification: false,
      citations: [],
    });

    const { result } = renderHook(() => useChat("session-5"));
    await act(async () => {
      await result.current.sendMessage("hello");
    });
    expect(result.current.messages).toHaveLength(2);

    act(() => {
      result.current.clearHistory();
    });

    expect(result.current.messages).toHaveLength(0);
    expect(localStorage.getItem("illiniguide.history.session-5")).toBeNull();
  });
});
