"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { fetchAnalyticsSummary } from "@/services/analyticsApi";
import type { AnalyticsSummary } from "@/types/analytics";

const DAY_PRESETS = [7, 30, 90] as const;

function topicLabel(topic: string): string {
  return topic.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatPercent(value: number | null): string {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

function formatMs(value: number | null): string {
  return value == null ? "—" : `${Math.round(value)}ms`;
}

interface StatTileProps {
  label: string;
  value: string;
}

function StatTile({ label, value }: StatTileProps) {
  return (
    <Card size="sm">
      <CardContent>
        <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
          {label}
        </p>
        <p className="font-heading text-2xl font-bold">{value}</p>
      </CardContent>
    </Card>
  );
}

export default function AnalyticsPage() {
  const [days, setDays] = useState<number>(30);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Resetting loading/error state before kicking off the fetch is the
  // standard fetch-on-deps-change pattern -- not an accidental cascade.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetchAnalyticsSummary(days)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load analytics.");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [days]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const chartData = summary?.topic_distribution.map((t) => ({
    topic: topicLabel(t.topic),
    count: t.count,
  }));

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 p-4 sm:p-8">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Back to chat"
            render={<Link href="/" />}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="font-heading text-xl font-bold tracking-tight uppercase">Analytics</h1>
        </div>
        <div className="flex items-center gap-1">
          {DAY_PRESETS.map((preset) => (
            <Button
              key={preset}
              variant={days === preset ? "default" : "outline"}
              size="sm"
              onClick={() => setDays(preset)}
            >
              {preset}d
            </Button>
          ))}
        </div>
      </header>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {isLoading ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : summary ? (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatTile label="Conversations" value={String(summary.total_conversations)} />
            <StatTile label="Questions Asked" value={String(summary.total_turns)} />
            <StatTile label="Grounded Rate" value={formatPercent(summary.grounded_rate)} />
            <StatTile
              label="Clarification Rate"
              value={formatPercent(summary.clarification_rate)}
            />
            <StatTile label="Corpus Size" value={String(summary.corpus_document_count)} />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Topic Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              {chartData && chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={Math.max(200, chartData.length * 32)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 24 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} />
                    <YAxis type="category" dataKey="topic" width={140} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="var(--color-primary)" radius={4} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-muted-foreground text-sm">No topic data yet.</p>
              )}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Feedback</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-1 text-sm">
                <p>Helpful: {summary.feedback.helpful}</p>
                <p>Not helpful: {summary.feedback.not_helpful}</p>
                <p>Ratio helpful: {formatPercent(summary.feedback.ratio_helpful)}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Latency</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-1 text-sm">
                <p>Average: {formatMs(summary.latency.avg_ms)}</p>
                <p>p50: {formatMs(summary.latency.p50_ms)}</p>
                <p>p95: {formatMs(summary.latency.p95_ms)}</p>
              </CardContent>
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
