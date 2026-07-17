import { ThumbsDown, ThumbsUp } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { FeedbackRating } from "@/types/chat";

interface FeedbackButtonsProps {
  feedback: FeedbackRating | undefined;
  onRate: (rating: FeedbackRating) => void;
}

export function FeedbackButtons({ feedback, onRate }: FeedbackButtonsProps) {
  if (feedback) {
    return (
      <p className="text-muted-foreground text-xs">
        {feedback === "helpful" ? "Thanks for the feedback!" : "Thanks -- we'll work on this."}
      </p>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => onRate("helpful")}
        aria-label="This answer was helpful"
        className="text-muted-foreground hover:text-foreground"
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="ghost"
        size="icon-xs"
        onClick={() => onRate("not_helpful")}
        aria-label="This answer was not helpful"
        className="text-muted-foreground hover:text-foreground"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </Button>
    </div>
  );
}
