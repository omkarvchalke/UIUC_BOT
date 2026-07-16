"use client";

import { ArrowUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto flex w-full max-w-2xl items-center gap-2">
      <Input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask about admissions, housing, financial aid..."
        disabled={disabled}
        maxLength={2000}
        className="h-11 rounded-full px-4"
        aria-label="Message"
      />
      <Button
        type="submit"
        size="icon"
        disabled={disabled || !value.trim()}
        className="shadow-primary/30 h-11 w-11 shrink-0 rounded-full shadow-lg disabled:shadow-none"
        aria-label="Send message"
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
    </form>
  );
}
