"use client";

import { GraduationCap, Globe2, Repeat, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { StudentType } from "@/types/chat";

interface StudentTypeOption {
  value: StudentType;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

const OPTIONS: StudentTypeOption[] = [
  {
    value: "freshman",
    label: "Freshman",
    description: "First year, new to UIUC",
    icon: Sparkles,
  },
  {
    value: "transfer",
    label: "Transfer",
    description: "Coming from another school",
    icon: Repeat,
  },
  {
    value: "graduate",
    label: "Graduate",
    description: "Master's or PhD student",
    icon: GraduationCap,
  },
  {
    value: "international",
    label: "International",
    description: "Studying on a visa",
    icon: Globe2,
  },
];

interface StudentTypeSelectorProps {
  onSelect: (studentType: StudentType | null) => void;
  isLoading: boolean;
}

export function StudentTypeSelector({ onSelect, isLoading }: StudentTypeSelectorProps) {
  return (
    <div className="mx-auto flex w-full max-w-lg flex-col items-center gap-6 px-4 text-center">
      <div className="space-y-2">
        <h1 className="font-heading text-2xl font-bold tracking-tight sm:text-3xl">
          Welcome to <span className="text-primary">IlliniGuide</span> AI
        </h1>
        <p className="text-muted-foreground text-sm leading-6">
          Answers about admissions, housing, financial aid, and more — grounded only in official
          UIUC sources. We never ask for your name, NetID, or any personal information.
        </p>
      </div>

      <Card className="brutal-border brutal-shadow w-full gap-3 rounded-3xl p-4">
        <p className="text-muted-foreground text-xs font-bold tracking-wide uppercase">
          What kind of student are you? (optional)
        </p>
        <div className="grid grid-cols-2 gap-3">
          {OPTIONS.map(({ value, label, description, icon: Icon }) => (
            <button
              key={value}
              type="button"
              disabled={isLoading}
              onClick={() => onSelect(value)}
              className="brutal-border brutal-shadow brutal-press hover:bg-accent flex flex-col items-start gap-1 rounded-2xl bg-card p-3 text-left disabled:pointer-events-none disabled:opacity-50"
            >
              <span className="bg-accent flex h-7 w-7 items-center justify-center rounded-full">
                <Icon className="text-primary h-4 w-4" />
              </span>
              <span className="text-sm font-bold">{label}</span>
              <span className="text-muted-foreground text-xs">{description}</span>
            </button>
          ))}
        </div>
      </Card>

      <Button
        variant="ghost"
        size="sm"
        disabled={isLoading}
        onClick={() => onSelect(null)}
        className="text-muted-foreground"
      >
        Skip for now
      </Button>
    </div>
  );
}
