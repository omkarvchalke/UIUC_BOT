import { useState } from "react";
import type { FeedbackRating } from "../types";

interface FeedbackOption {
  rating: FeedbackRating;
  label: string;
}

const OPTIONS: FeedbackOption[] = [
  { rating: "helpful", label: "Helpful" },
  { rating: "not_helpful", label: "Not Helpful" },
  { rating: "wrong_source", label: "Wrong Source" },
  { rating: "missing_information", label: "Missing Information" },
];

type Status = "idle" | "submitting" | "sent" | "error";

export default function FeedbackButtons({
  onSubmit,
}: {
  onSubmit: (rating: FeedbackRating) => Promise<void>;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [selected, setSelected] = useState<FeedbackRating | null>(null);

  const handleClick = async (rating: FeedbackRating) => {
    setSelected(rating);
    setStatus("submitting");
    try {
      await onSubmit(rating);
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  };

  if (status === "sent") {
    return <p className="text-xs text-slate-500">Thanks for your feedback.</p>;
  }

  if (status === "error") {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className="text-red-600">Couldn't send feedback.</span>
        <button
          type="button"
          onClick={() => selected && handleClick(selected)}
          className="font-medium text-brand-600 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-slate-500">Was this helpful?</span>
      {OPTIONS.map((option) => (
        <button
          key={option.rating}
          type="button"
          disabled={status === "submitting"}
          onClick={() => handleClick(option.rating)}
          className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 transition hover:border-brand-500 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
