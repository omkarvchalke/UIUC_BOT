"use client";

import { useCallback, useEffect, useState } from "react";

import { sendChatMessage } from "@/services/chatApi";
import type { ChatMessage } from "@/types/chat";

function historyKey(sessionId: string): string {
  return `illiniguide.history.${sessionId}`;
}

function loadHistory(sessionId: string): ChatMessage[] {
  try {
    const raw = localStorage.getItem(historyKey(sessionId));
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(sessionId: string, messages: ChatMessage[]): void {
  localStorage.setItem(historyKey(sessionId), JSON.stringify(messages));
}

function createId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

interface UseChatResult {
  messages: ChatMessage[];
  isSending: boolean;
  error: string | null;
  sendMessage: (text: string) => Promise<void>;
  clearHistory: () => void;
}

export function useChat(sessionId: string | null): UseChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Conversation history lives client-side (localStorage per session_id),
  // not fetched from the backend checkpointer: the checkpointer stores
  // messages but not per-message citations, so a backend history endpoint
  // would lose citation data on reload that client-side storage keeps.
  // Reading localStorage can only happen after mount (SSR has no access to
  // it), so this sync-on-mount effect is the standard, hydration-safe
  // tradeoff -- not the anti-pattern react-hooks/set-state-in-effect
  // usually flags.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    setMessages(sessionId ? loadHistory(sessionId) : []);
  }, [sessionId]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!sessionId || !trimmed || isSending) return;

      const userMessage: ChatMessage = {
        id: createId(),
        role: "user",
        content: trimmed,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => {
        const next = [...prev, userMessage];
        saveHistory(sessionId, next);
        return next;
      });
      setIsSending(true);
      setError(null);

      try {
        const response = await sendChatMessage(sessionId, trimmed);
        const assistantMessage: ChatMessage = {
          id: createId(),
          role: "assistant",
          content: response.answer,
          citations: response.citations,
          grounded: response.grounded,
          needsClarification: response.needs_clarification,
          createdAt: new Date().toISOString(),
        };
        setMessages((prev) => {
          const next = [...prev, assistantMessage];
          saveHistory(sessionId, next);
          return next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
      } finally {
        setIsSending(false);
      }
    },
    [sessionId, isSending],
  );

  const clearHistory = useCallback(() => {
    if (sessionId) {
      localStorage.removeItem(historyKey(sessionId));
    }
    setMessages([]);
  }, [sessionId]);

  return { messages, isSending, error, sendMessage, clearHistory };
}
