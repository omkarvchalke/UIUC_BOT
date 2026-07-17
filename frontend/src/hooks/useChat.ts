"use client";

import { useCallback, useEffect, useState } from "react";

import { sendChatMessage, sendFeedback } from "@/services/chatApi";
import type { ChatMessage, FeedbackRating } from "@/types/chat";

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
  // Returns whether the send succeeded, so callers (ChatInput) can decide
  // whether to clear the composer or restore the user's text for a retry.
  sendMessage: (text: string) => Promise<boolean>;
  clearHistory: () => void;
  submitFeedback: (messageId: string, rating: FeedbackRating) => Promise<void>;
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
      if (!sessionId || !trimmed || isSending) return false;

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
          topic: response.topic,
          classificationConfidence: response.classification_confidence,
          createdAt: new Date().toISOString(),
          question: trimmed,
        };
        setMessages((prev) => {
          const next = [...prev, assistantMessage];
          saveHistory(sessionId, next);
          return next;
        });
        return true;
      } catch (err) {
        // Roll back the optimistically-added user message too -- otherwise
        // it's stuck in the transcript unanswered with no way to retry it
        // (the composer would have a fresh, empty retry of the same text
        // sitting right below a "failed" copy of itself).
        setMessages((prev) => {
          const next = prev.filter((m) => m.id !== userMessage.id);
          saveHistory(sessionId, next);
          return next;
        });
        setError(err instanceof Error ? err.message : "Something went wrong. Please try again.");
        return false;
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

  const submitFeedback = useCallback(
    async (messageId: string, rating: FeedbackRating) => {
      if (!sessionId) return;
      const message = messages.find((m) => m.id === messageId);
      if (!message || message.role !== "assistant" || message.feedback) return;

      // Optimistic: mark as rated immediately so the buttons update without
      // waiting on the network, matching the rest of this hook's pattern of
      // updating local state (and persisting it) right away.
      setMessages((prev) => {
        const next = prev.map((m) => (m.id === messageId ? { ...m, feedback: rating } : m));
        saveHistory(sessionId, next);
        return next;
      });

      try {
        await sendFeedback({
          session_id: sessionId,
          message_id: messageId,
          question: message.question ?? "",
          answer: message.content,
          rating,
        });
      } catch {
        // Feedback is a nice-to-have signal, not a critical path -- revert
        // the optimistic mark on failure so the student can retry, but
        // don't surface a disruptive error for a background action.
        setMessages((prev) => {
          const next = prev.map((m) =>
            m.id === messageId ? { ...m, feedback: undefined } : m,
          );
          saveHistory(sessionId, next);
          return next;
        });
      }
    },
    [sessionId, messages],
  );

  return { messages, isSending, error, sendMessage, clearHistory, submitFeedback };
}
