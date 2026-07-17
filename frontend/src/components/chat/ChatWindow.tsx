"use client";

import { useEffect, useRef, useState } from "react";

import { MessageBubble } from "@/components/chat/MessageBubble";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMessage, FeedbackRating } from "@/types/chat";

interface ChatWindowProps {
  messages: ChatMessage[];
  isSending: boolean;
  onRateFeedback?: (messageId: string, rating: FeedbackRating) => void;
  debugMode?: boolean;
}

// Real p95 latency on this app is ~18s (see the analytics dashboard) -- the
// typing dots alone don't distinguish "still working" from "stuck" once a
// wait runs that long, so a hint kicks in partway through a typical wait.
const SLOW_ANSWER_HINT_DELAY_MS = 5000;

// Strips the answer down to plain, speakable text for the screen-reader
// announcement -- the visible bubble still renders full markdown via
// ReactMarkdown, but a live region reading "asterisk asterisk bold
// asterisk asterisk" aloud would be worse than not announcing at all.
function toPlainTextExcerpt(markdown: string, maxLen = 200): string {
  const plain = markdown
    .replace(/[#*_`>~]/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\s+/g, " ")
    .trim();
  return plain.length > maxLen ? `${plain.slice(0, maxLen)}…` : plain;
}

export function ChatWindow({ messages, isSending, onRateFeedback, debugMode }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [showSlowHint, setShowSlowHint] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isSending]);

  useEffect(() => {
    if (!isSending) return;
    const timer = setTimeout(() => setShowSlowHint(true), SLOW_ANSWER_HINT_DELAY_MS);
    return () => {
      clearTimeout(timer);
      setShowSlowHint(false);
    };
  }, [isSending]);

  const lastMessage = messages[messages.length - 1];
  // Only announces once sending has settled -- not on initial mount (the
  // existing history is already in the DOM, so no "change" to announce)
  // and not while a request is in flight (the typing dots already convey
  // that state visually and don't need a live-region echo).
  const announcement =
    !isSending && lastMessage?.role === "assistant"
      ? `IlliniAssist: ${toPlainTextExcerpt(lastMessage.content)}`
      : "";

  return (
    <ScrollArea className="h-full w-full">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 px-4 py-6">
        {messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onRateFeedback={onRateFeedback}
            debugMode={debugMode}
          />
        ))}
        {isSending && (
          <div className="flex flex-col items-start gap-1">
            <div className="bg-muted rounded-2xl rounded-bl-sm px-3 py-1">
              <TypingIndicator />
            </div>
            {showSlowHint && (
              <p className="text-muted-foreground px-1 text-xs">
                Still thinking — complex questions can take up to 15 seconds.
              </p>
            )}
          </div>
        )}
        <div ref={bottomRef} />
        <div role="status" aria-live="polite" className="sr-only">
          {announcement}
        </div>
      </div>
    </ScrollArea>
  );
}
