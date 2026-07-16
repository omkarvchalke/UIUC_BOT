export function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-2" aria-label="IlliniAssist AI is typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="bg-primary h-1.5 w-1.5 animate-bounce rounded-full"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}
