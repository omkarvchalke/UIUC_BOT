from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.chat_turn_event import ChatTurnIntent
from app.models.document import SourceType, Topic
from app.models.feedback import FeedbackRating
from app.repositories.chat_turn_event_repository import ChatTurnEventRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.session_repository import SessionRepository


async def test_analytics_summary_on_empty_corpus() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analytics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_conversations"] == 0
    assert body["total_turns"] == 0
    assert body["grounded_rate"] is None
    assert body["clarification_rate"] is None
    assert body["topic_distribution"] == []
    assert body["feedback"] == {"helpful": 0, "not_helpful": 0, "ratio_helpful": None}
    assert body["latency"] == {"avg_ms": None, "p50_ms": None, "p95_ms": None}
    assert body["corpus_document_count"] == 0


async def test_analytics_summary_reflects_seeded_data(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        conversation = await SessionRepository(session).create(
            student_type=None, semester=None, college=None, department=None
        )
        await ChatTurnEventRepository(session).create(
            session_id=conversation.id,
            intent=ChatTurnIntent.QUESTION,
            topic=Topic.HOUSING,
            needs_clarification=False,
            grounded=True,
            citation_count=1,
            latency_ms=150.0,
        )
        await FeedbackRepository(session).create(
            session_id=conversation.id,
            message_id="msg-1",
            question="Where do freshmen live?",
            answer="In undergraduate residence halls.",
            rating=FeedbackRating.HELPFUL,
            comment=None,
        )
        await DocumentRepository(session).upsert_document(
            url="https://example.illinois.edu/housing",
            title="Housing",
            department="University Housing",
            topic=Topic.HOUSING,
            source_type=SourceType.HTML,
            student_types=(),
            last_updated=None,
            content_hash="hash-housing",
        )
        # upsert_document only flushes; it relies on a caller-level commit
        # (normally replace_chunks, which this test doesn't call).
        await session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analytics/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["total_conversations"] == 1
    assert body["total_turns"] == 1
    assert body["grounded_rate"] == 1.0
    assert body["clarification_rate"] == 0.0
    assert body["topic_distribution"] == [{"topic": "housing", "count": 1}]
    assert body["feedback"] == {"helpful": 1, "not_helpful": 0, "ratio_helpful": 1.0}
    assert body["latency"]["avg_ms"] == 150.0
    assert body["corpus_document_count"] == 1


async def test_analytics_summary_respects_days_param() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/analytics/summary", params={"days": 7})

    assert response.status_code == 200
