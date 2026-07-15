import { AlertTriangle, HelpCircle } from "lucide-react";

import { SourcePanel } from "@/components/chat/SourcePanel";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-6 sm:max-w-[75%]",
          isUser ? "bg-primary text-primary-foreground rounded-br-sm" : "bg-muted rounded-bl-sm",
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
      </div>
    </div>
  );
}
