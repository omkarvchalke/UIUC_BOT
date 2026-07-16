from datetime import datetime

from pydantic import BaseModel

from app.models.document import Topic


class TopicCount(BaseModel):
    topic: Topic
    count: int


class LatencyStats(BaseModel):
    avg_ms: float | None
    p50_ms: float | None
    p95_ms: float | None


class FeedbackBreakdown(BaseModel):
    helpful: int
    not_helpful: int
    ratio_helpful: float | None  # None when total == 0, not a divide-by-zero 0.0


class AnalyticsSummary(BaseModel):
    since: datetime | None
    total_conversations: int
    total_turns: int
    grounded_rate: float | None
    clarification_rate: float | None
    topic_distribution: list[TopicCount]
    feedback: FeedbackBreakdown
    latency: LatencyStats
    corpus_document_count: int
