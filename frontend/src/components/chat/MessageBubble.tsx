import { AlertTriangle, Bug, HelpCircle } from "lucide-react";

import { FeedbackButtons } from "@/components/chat/FeedbackButtons";
import { SourcePanel } from "@/components/chat/SourcePanel";
import { cn } from "@/lib/utils";
import type { ChatMessage, FeedbackRating } from "@/types/chat";

interface MessageBubbleProps {
  message: ChatMessage;
  onRateFeedback?: (messageId: string, rating: FeedbackRating) => void;
  debugMode?: boolean;
}

export function MessageBubble({ message, onRateFeedback, debugMode }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          // brutal-border, not brutal-shadow: a bold outline keeps bubbles
          // consistent with the rest of the theme without a wall of hard
          // offset shadows down a scrolling conversation.
          "brutal-border max-w-[85%] rounded-3xl px-4 py-2.5 text-sm leading-6 sm:max-w-[75%]",
          isUser
            ? "bg-primary text-primary-foreground rounded-br-md"
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

        {!isUser && debugMode && message.topic && (
          <div className="text-muted-foreground mt-2 flex items-center gap-1 text-xs">
            <Bug className="h-3 w-3" />
            Topic: {message.topic}
            {message.classificationConfidence != null &&
              ` (${message.classificationConfidence.toFixed(2)})`}
          </div>
        )}

        {!isUser && message.citations && message.citations.length > 0 && (
          <SourcePanel citations={message.citations} debugMode={debugMode} />
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
