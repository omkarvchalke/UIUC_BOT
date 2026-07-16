import { getApiBaseUrl } from "@/services/api";
import type { AnalyticsSummary } from "@/types/analytics";

export async function fetchAnalyticsSummary(days?: number): Promise<AnalyticsSummary> {
  const url = new URL(`${getApiBaseUrl()}/api/v1/analytics/summary`);
  if (days) {
    url.searchParams.set("days", String(days));
  }

  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Analytics summary failed with status ${response.status}`);
  }

  return response.json();
}
