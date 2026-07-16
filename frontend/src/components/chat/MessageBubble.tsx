import { AlertTriangle, HelpCircle } from "lucide-react";

import { FeedbackButtons } from "@/components/chat/FeedbackButtons";
import { SourcePanel } from "@/components/chat/SourcePanel";
import { cn } from "@/lib/utils";
import type { ChatMessage, FeedbackRating } from "@/types/chat";

interface MessageBubbleProps {
  message: ChatMessage;
  onRateFeedback?: (messageId: string, rating: FeedbackRating) => void;
}

export function MessageBubble({ message, onRateFeedback }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-3xl px-4 py-2.5 text-sm leading-6 sm:max-w-[75%]",
          isUser
            ? "bg-primary text-primary-foreground shadow-primary/20 rounded-br-md shadow-md"
            : "bg-muted rounded-bl-md",
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {!isUser && message.needsClarification && (
          <div className="text-muted-foreground mt-2 flex items-center gap-1 text-xs">
            <HelpCircle className="h-3 w-3" />
            Clarifying question
          </div>
        )}

        {!isUser && message.grounded === false && !message.needsClarification && (
          <div className="mt-2 flex items-center gap-1 text-xs text-amber-600 dark:text-amber-400">
            <AlertTriangle className="h-3 w-3" />
            This answer may be incomplete
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <SourcePanel citations={message.citations} />
        )}

        {!isUser && !message.needsClarification && onRateFeedback && (
          <FeedbackButtons
            feedback={message.feedback}
            onRate={(rating) => onRateFeedback(message.id, rating)}
          />
        )}
      </div>
    </div>
  );
}
