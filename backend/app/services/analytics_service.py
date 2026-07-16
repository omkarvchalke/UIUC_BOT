import uuid
from datetime import datetime

from app.models.chat_turn_event import ChatTurnIntent
from app.models.document import Topic
from app.models.feedback import FeedbackRating
from app.repositories.chat_turn_event_repository import ChatTurnEventRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.analytics import (
    AnalyticsSummary,
    FeedbackBreakdown,
    LatencyStats,
    TopicCount,
)


class AnalyticsService:
    """Business logic for the analytics dashboard. Routes never touch the
    repositories directly."""

    def __init__(
        self,
        chat_turn_event_repository: ChatTurnEventRepository,
        session_repository: SessionRepository,
        feedback_repository: FeedbackRepository,
        document_repository: DocumentRepository,
    ) -> None:
        self._chat_turn_events = chat_turn_event_repository
        self._sessions = session_repository
        self._feedback = feedback_repository
        self._documents = document_repository

    async def record_turn(
        self,
        *,
        session_id: uuid.UUID,
        intent: ChatTurnIntent,
        topic: Topic | None,
        needs_clarification: bool,
        grounded: bool | None,
        citation_count: int,
        latency_ms: float | None,
    ) -> None:
        await self._chat_turn_events.create(
            session_id=session_id,
            intent=intent,
            topic=topic,
            needs_clarification=needs_clarification,
            grounded=grounded,
            citation_count=citation_count,
            latency_ms=latency_ms,
        )

    async def get_summary(self, *, since: datetime | None) -> AnalyticsSummary:
        # Sequential, not asyncio.gather: every repository here shares one
        # AsyncSession per request (see app/api/dependencies.py's DbSession),
        # and SQLAlchemy's AsyncSession is not safe for concurrent use from
        # multiple coroutines at once -- gather()ing these would race on the
        # same underlying asyncpg connection.
        total_conversations = await self._sessions.count_sessions(since=since)
        total_turns = await self._chat_turn_events.count_turns(since=since)
        grounded_rate = await self._chat_turn_events.grounded_rate(since=since)
        clarification_rate = await self._chat_turn_events.clarification_rate(since=since)
        topic_counts = await self._chat_turn_events.topic_distribution(since=since)
        feedback_counts = await self._feedback.count_by_rating(since=since)
        latency = await self._chat_turn_events.latency_stats(since=since)
        corpus_document_count = await self._documents.count_documents()

        helpful = feedback_counts.get(FeedbackRating.HELPFUL, 0)
        not_helpful = feedback_counts.get(FeedbackRating.NOT_HELPFUL, 0)
        total_feedback = helpful + not_helpful
        avg_ms, p50_ms, p95_ms = latency

        return AnalyticsSummary(
            since=since,
            total_conversations=total_conversations,
            total_turns=total_turns,
            grounded_rate=grounded_rate,
            clarification_rate=clarification_rate,
            topic_distribution=[
                TopicCount(topic=topic, count=count) for topic, count in topic_counts
            ],
            feedback=FeedbackBreakdown(
                helpful=helpful,
                not_helpful=not_helpful,
                ratio_helpful=(helpful / total_feedback) if total_feedback else None,
            ),
            latency=LatencyStats(avg_ms=avg_ms, p50_ms=p50_ms, p95_ms=p95_ms),
            corpus_document_count=corpus_document_count,
        )
