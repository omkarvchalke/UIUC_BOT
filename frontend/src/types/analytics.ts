export interface TopicCount {
  topic: string;
  count: number;
}

export interface LatencyStats {
  avg_ms: number | null;
  p50_ms: number | null;
  p95_ms: number | null;
}

export interface FeedbackBreakdown {
  helpful: number;
  not_helpful: number;
  ratio_helpful: number | null;
}

export interface AnalyticsSummary {
  since: string | null;
  total_conversations: number;
  total_turns: number;
  grounded_rate: number | null;
  clarification_rate: number | null;
  topic_distribution: TopicCount[];
  feedback: FeedbackBreakdown;
  latency: LatencyStats;
  corpus_document_count: number;
}
