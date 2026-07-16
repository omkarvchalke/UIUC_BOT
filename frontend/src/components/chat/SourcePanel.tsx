"use client";

import { BookOpen, ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { Citation } from "@/types/chat";

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

interface SourcePanelProps {
  citations: Citation[];
  debugMode?: boolean;
}

export function SourcePanel({ citations, debugMode }: SourcePanelProps) {
  if (citations.length === 0) return null;

  return (
    <Sheet>
      <SheetTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            className="brutal-border brutal-shadow-sm brutal-press mt-2 h-7 gap-1.5 rounded-full text-xs font-bold"
          />
        }
      >
        <BookOpen className="h-3.5 w-3.5" />
        {citations.length} {citations.length === 1 ? "source" : "sources"}
      </SheetTrigger>
      <SheetContent side="right" className="w-full sm:max-w-sm">
        <SheetHeader>
          <SheetTitle className="font-heading uppercase">Sources</SheetTitle>
        </SheetHeader>
        <div className="flex flex-col gap-3 overflow-y-auto px-4 pb-4">
          {citations.map((citation, i) => (
            <a
              key={`${citation.url}-${i}`}
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="brutal-border brutal-shadow-sm brutal-press hover:bg-accent bg-card flex flex-col gap-1.5 rounded-2xl p-3"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm leading-5 font-bold">{citation.title}</span>
                <ExternalLink className="text-muted-foreground mt-0.5 h-3.5 w-3.5 shrink-0" />
              </div>
              <span className="text-muted-foreground text-xs">{citation.department}</span>
              <Badge variant="secondary" className="w-fit text-[10px]">
                {topicLabel(citation.topic)}
              </Badge>
              {debugMode && (
                <div className="text-muted-foreground flex flex-wrap gap-x-2 gap-y-0.5 text-[10px]">
                  {citation.subtopic && <span>{topicLabel(citation.subtopic)}</span>}
                  {citation.fused_score != null && (
                    <span>fused: {citation.fused_score.toFixed(3)}</span>
                  )}
                  {citation.rerank_score != null && (
                    <span>rerank: {citation.rerank_score.toFixed(3)}</span>
                  )}
                </div>
              )}
            </a>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}
