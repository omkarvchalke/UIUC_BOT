"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ChatInputProps {
  // Resolves to whether the send succeeded, so the composer knows whether
  // to clear itself or restore the user's text for a retry.
  onSend: (message: string) => Promise<boolean> | void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  // Return focus to the composer as soon as it's usable again -- on first
  // mount (right after picking a student type) and after each answer
  // finishes coming back -- so a student can keep typing without reaching
  // for the mouse between questions. Skipped on touch devices: there's no
  // mouse to reach for, and focusing a text input pops the virtual
  // keyboard, which would otherwise slide up uninvited after every answer.
  useEffect(() => {
    if (disabled) return;
    const isTouchDevice =
      typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;
    if (isTouchDevice) return;
    inputRef.current?.focus();
  }, [disabled]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    setValue("");
    const succeeded = await onSend(trimmed);
    if (succeeded === false) {
      // Restore the text rather than making the student retype it --
      // sending only fails on a network/backend error, not user error.
      setValue(trimmed);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mx-auto flex w-full max-w-3xl items-center gap-2">
      <Input
        ref={inputRef}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="Ask about admissions, housing, financial aid..."
        disabled={disabled}
        maxLength={2000}
        className="brutal-border h-11 rounded-full bg-card px-4"
        aria-label="Message"
      />
      <Button
        type="submit"
        size="icon"
        disabled={disabled || !value.trim()}
        className="brutal-border brutal-shadow brutal-press h-11 w-11 shrink-0 rounded-full disabled:shadow-none"
        aria-label="Send message"
      >
        <ArrowUp className="h-4 w-4" />
      </Button>
    </form>
  );
}
