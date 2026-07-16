import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { fetchAnalyticsSummary } from "./analyticsApi";
import type { AnalyticsSummary } from "@/types/analytics";

function makeSummary(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  return {
    since: null,
    total_conversations: 3,
    total_turns: 5,
    grounded_rate: 0.8,
    clarification_rate: 0.1,
    topic_distribution: [{ topic: "housing", count: 2 }],
    feedback: { helpful: 4, not_helpful: 1, ratio_helpful: 0.8 },
    latency: { avg_ms: 150, p50_ms: 120, p95_ms: 300 },
    corpus_document_count: 42,
    ...overrides,
  };
}

describe("fetchAnalyticsSummary", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => makeSummary(),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requests the analytics summary endpoint", async () => {
    await fetchAnalyticsSummary();

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toBe("http://localhost:8000/api/v1/analytics/summary");
  });

  it("includes the days param when provided", async () => {
    await fetchAnalyticsSummary(7);

    const [url] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toBe("http://localhost:8000/api/v1/analytics/summary?days=7");
  });

  it("returns the parsed summary", async () => {
    const result = await fetchAnalyticsSummary();

    expect(result.total_conversations).toBe(3);
    expect(result.topic_distribution).toEqual([{ topic: "housing", count: 2 }]);
  });

  it("throws when the response is not ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }),
    );

    await expect(fetchAnalyticsSummary()).rejects.toThrow("500");
  });
});
