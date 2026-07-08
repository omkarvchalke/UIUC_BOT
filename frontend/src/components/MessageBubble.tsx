import type { ChatMessage, FeedbackRating } from "../types";
import BotAvatar from "./BotAvatar";
import SourceChip from "./SourceChip";
import ConfidenceBadge from "./ConfidenceBadge";
import FeedbackButtons from "./FeedbackButtons";

export default function MessageBubble({
  message,
  onFeedback,
}: {
  message: ChatMessage;
  onFeedback?: (rating: FeedbackRating) => Promise<void>;
}) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-brand-600 px-4 py-2 text-sm text-white">
          {message.question}
        </div>
      </div>
    );
  }

  if (message.error) {
    return (
      <div className="flex items-start gap-2">
        <BotAvatar />
        <div className="max-w-[80%] rounded-2xl rounded-bl-sm border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
          {message.error}
        </div>
      </div>
    );
  }

  const response = message.response;
  if (!response) return null;

  const isStreaming = Boolean(message.streaming);

  return (
    <div className="flex items-start gap-2">
      <BotAvatar />
      <div className="max-w-[85%] space-y-3 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
        {!isStreaming && (
          <div className="flex items-center justify-between gap-2">
            <ConfidenceBadge level={response.confidence} />
            {response.requires_official_confirmation && (
              <span className="text-xs font-medium text-amber-700">
                Official confirmation recommended
              </span>
            )}
          </div>
        )}

        <p className="whitespace-pre-wrap text-slate-800">
          {response.answer}
          {isStreaming && (
            <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-slate-400 align-middle" />
          )}
        </p>

        {!isStreaming && response.next_steps.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Next steps
            </p>
            <ul className="mt-1 list-inside list-disc space-y-1 text-slate-700">
              {response.next_steps.map((step, idx) => (
                <li key={idx}>{step}</li>
              ))}
            </ul>
          </div>
        )}

        {!isStreaming && response.sources.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-2">
            <span className="text-xs text-slate-400">Sources:</span>
            {response.sources.map((source) => (
              <SourceChip key={source.url} source={source} />
            ))}
          </div>
        )}

        {!isStreaming && onFeedback && <FeedbackButtons onSubmit={onFeedback} />}
      </div>
    </div>
  );
}
