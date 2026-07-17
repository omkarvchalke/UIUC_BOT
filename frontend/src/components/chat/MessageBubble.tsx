import { AlertTriangle, Bug, Check, Copy, HelpCircle } from "lucide-react";
import { type RefObject, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { FeedbackButtons } from "@/components/chat/FeedbackButtons";
import { SourcePanel } from "@/components/chat/SourcePanel";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ChatMessage, FeedbackRating } from "@/types/chat";

interface MessageBubbleProps {
  message: ChatMessage;
  onRateFeedback?: (messageId: string, rating: FeedbackRating) => void;
  debugMode?: boolean;
}

// Answers may cite external source URLs -- open them in a new tab, and
// harden against reverse-tabnabbing the same way any other external link
// in this app would be.
const MARKDOWN_COMPONENTS: Components = {
  a: ({ children, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

function CopyAnswerButton({
  content,
  contentRef,
}: {
  content: string;
  contentRef: RefObject<HTMLElement | null>;
}) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(content);
    setCopied(true);

    // Select the answer text in the DOM so the browser's native selection
    // highlight shows exactly what was copied -- the same visual cue a
    // manual select-then-copy would give.
    const node = contentRef.current;
    const selection = window.getSelection();
    if (node && selection) {
      const range = document.createRange();
      range.selectNodeContents(node);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    setTimeout(() => {
      setCopied(false);
      window.getSelection()?.removeAllRanges();
    }, 1500);
  }

  return (
    <Button
      variant="ghost"
      size="icon-xs"
      onClick={handleCopy}
      aria-label={copied ? "Copied" : "Copy answer"}
      className="text-muted-foreground hover:text-foreground"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </Button>
  );
}

export function MessageBubble({ message, onRateFeedback, debugMode }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const contentRef = useRef<HTMLDivElement>(null);

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
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div ref={contentRef} className="prose-chat">
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}

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

        {!isUser && !message.needsClarification && (
          <div className="mt-2 flex items-center gap-1">
            <CopyAnswerButton content={message.content} contentRef={contentRef} />
            {onRateFeedback && (
              <FeedbackButtons
                feedback={message.feedback}
                onRate={(rating) => onRateFeedback(message.id, rating)}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
