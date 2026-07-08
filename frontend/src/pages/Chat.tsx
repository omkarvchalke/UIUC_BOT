import { useEffect, useRef, useState } from "react";
import DisclaimerBanner from "../components/DisclaimerBanner";
import PrivacyBanner from "../components/PrivacyBanner";
import ChatBox from "../components/ChatBox";
import MessageBubble from "../components/MessageBubble";
import BotAvatar from "../components/BotAvatar";
import { streamChatMessage, submitFeedback } from "../services/api";
import type { ChatMessage, ChatTurn, FeedbackRating } from "../types";

const SAMPLE_QUESTIONS = [
  "When is Welcome Week?",
  "Do first-year students have to live on campus?",
  "How do I apply for housing?",
  "What is international student check-in?",
  "How do I get an i-card?",
  "Can students ride the bus with an i-card?",
  "Can you check my admission status?",
];

// How many prior turns to send as conversation history — enough for
// natural follow-ups without letting the prompt grow unbounded across a
// long session (backend also caps ChatRequest.history at 20 turns).
const MAX_HISTORY_TURNS = 8;

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-2">
      <BotAvatar />
      <div className="flex items-center gap-1 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 animate-bounce rounded-full bg-slate-400"
            style={{ animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  );
}

function buildHistory(messages: ChatMessage[]): ChatTurn[] {
  const turns: ChatTurn[] = [];
  for (const message of messages) {
    if (message.role === "user" && message.question) {
      turns.push({ role: "user", content: message.question });
    } else if (message.role === "assistant" && message.response && !message.streaming) {
      turns.push({ role: "assistant", content: message.response.answer });
    }
  }
  return turns.slice(-MAX_HISTORY_TURNS);
}

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (question: string) => {
    const history = buildHistory(messages);
    const userMessage: ChatMessage = { id: createId(), role: "user", question };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    const assistantId = createId();
    let started = false;

    await streamChatMessage(question, history, {
      onDelta: (text) => {
        setLoading(false);
        if (!started) {
          started = true;
          setMessages((prev) => [
            ...prev,
            {
              id: assistantId,
              role: "assistant",
              question,
              streaming: true,
              response: {
                answer: text,
                sources: [],
                confidence: "low",
                next_steps: [],
                requires_official_confirmation: false,
              },
            },
          ]);
          return;
        }
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.response
              ? { ...m, response: { ...m.response, answer: m.response.answer + text } }
              : m,
          ),
        );
      },
      onDone: (event) => {
        setLoading(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId && m.response
              ? {
                  ...m,
                  streaming: false,
                  response: {
                    ...m.response,
                    sources: event.sources,
                    confidence: event.confidence,
                    next_steps: event.next_steps,
                    requires_official_confirmation: event.requires_official_confirmation,
                  },
                }
              : m,
          ),
        );
      },
      onError: (detail) => {
        setLoading(false);
        setMessages((prev) => {
          const withoutPartial = prev.filter((m) => m.id !== assistantId);
          return [
            ...withoutPartial,
            {
              id: createId(),
              role: "assistant",
              error: started
                ? `Something went wrong while generating the rest of the answer: ${detail}`
                : "Sorry, something went wrong reaching the backend. Please make sure the API server is running and try again.",
            },
          ];
        });
      },
    });
  };

  const handleFeedback = async (message: ChatMessage, rating: FeedbackRating) => {
    if (!message.question || !message.response) return;
    // Let failures propagate to FeedbackButtons so it can show a real
    // error state instead of always claiming success.
    await submitFeedback({
      question: message.question,
      answer: message.response.answer,
      rating,
      source_titles: message.response.sources.map((s) => s.title),
    });
  };

  return (
    <div className="flex h-[calc(100vh-11rem)] flex-col gap-4">
      <DisclaimerBanner />

      <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
        <div className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <BotAvatar />
          <div>
            <p className="text-sm font-semibold text-slate-900">CampusGuide AI</p>
            <p className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Unofficial assistant · public UIUC info only
            </p>
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.length === 0 && (
            <div className="space-y-3">
              <p className="text-sm text-slate-500">Try a sample question:</p>
              <div className="flex flex-wrap gap-2">
                {SAMPLE_QUESTIONS.map((question) => (
                  <button
                    key={question}
                    type="button"
                    onClick={() => handleSend(question)}
                    className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs text-slate-600 transition hover:border-brand-500 hover:text-brand-700"
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              onFeedback={
                message.role === "assistant" && message.response
                  ? (rating) => handleFeedback(message, rating)
                  : undefined
              }
            />
          ))}

          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      </div>

      <PrivacyBanner />
      <ChatBox
        onSend={handleSend}
        disabled={loading || messages.some((m) => m.streaming)}
      />
    </div>
  );
}
