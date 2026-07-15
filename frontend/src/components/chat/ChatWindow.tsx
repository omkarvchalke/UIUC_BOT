"use client";

import { useEffect, useRef } from "react";

import { MessageBubble } from "@/components/chat/MessageBubble";
import { TypingIndicator } from "@/components/chat/TypingIndicator";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { ChatMessage, FeedbackRating } from "@/types/chat";

interface ChatWindowProps {
  messages: ChatMessage[];
  isSending: boolean;
  onRateFeedback?: (messageId: string, rating: FeedbackRating) => void;
}

export function ChatWindow({ messages, isSending, onRateFeedback }: ChatWindowProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isSending]);

  return (
    <ScrollArea className="h-full w-full">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-6">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} onRateFeedback={onRateFeedback} />
        ))}
        {isSending && (
          <div className="flex justify-start">
            <div className="bg-muted rounded-2xl rounded-bl-sm px-3 py-1">
              <TypingIndicator />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
