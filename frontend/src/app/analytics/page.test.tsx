import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import * as analyticsApi from "@/services/analyticsApi";
import type { AnalyticsSummary } from "@/types/analytics";

import AnalyticsPage from "./page";

function makeSummary(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  return {
    since: null,
    total_conversations: 12,
    total_turns: 30,
    grounded_rate: 0.75,
    clarification_rate: 0.2,
    topic_distribution: [
      { topic: "housing", count: 5 },
      { topic: "financial_aid", count: 3 },
    ],
    feedback: { helpful: 8, not_helpful: 2, ratio_helpful: 0.8 },
    latency: { avg_ms: 200, p50_ms: 180, p95_ms: 400 },
    corpus_document_count: 100,
    ...overrides,
  };
}

describe("AnalyticsPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders stat tiles with the fetched summary values", async () => {
    vi.spyOn(analyticsApi, "fetchAnalyticsSummary").mockResolvedValue(makeSummary());

    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("12")).toBeInTheDocument());
    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("renders an empty topic-distribution message when there is no data yet", async () => {
    vi.spyOn(analyticsApi, "fetchAnalyticsSummary").mockResolvedValue(
      makeSummary({ topic_distribution: [] }),
    );

    render(<AnalyticsPage />);

    await waitFor(() => expect(screen.getByText("No topic data yet.")).toBeInTheDocument());
  });

  it("shows an error message when the fetch fails", async () => {
    vi.spyOn(analyticsApi, "fetchAnalyticsSummary").mockRejectedValue(
      new Error("Analytics summary failed with status 500"),
    );

    render(<AnalyticsPage />);

    await waitFor(() =>
      expect(screen.getByText(/Analytics summary failed with status 500/)).toBeInTheDocument(),
    );
  });
});
