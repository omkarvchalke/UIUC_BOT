const QUESTIONS = [
  "How do I apply as a freshman?",
  "Where do freshmen live on campus?",
  "What meal plans are available?",
  "How do I apply for OPT?",
  "What are the library hours?",
  "How do I get a parking permit?",
];

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export function SuggestedQuestions({ onSelect, disabled }: SuggestedQuestionsProps) {
  return (
    <div className="mx-auto flex w-full max-w-2xl flex-wrap justify-center gap-2 px-4">
      {QUESTIONS.map((question) => (
        <button
          key={question}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(question)}
          className="border-input hover:border-primary hover:bg-accent rounded-full border px-3.5 py-1.5 text-sm transition-all hover:-translate-y-0.5 hover:shadow-sm active:translate-y-0 disabled:pointer-events-none disabled:opacity-50"
        >
          {question}
        </button>
      ))}
    </div>
  );
}
