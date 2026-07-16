from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.chat_turn_event import ChatTurnIntent
from app.models.conversation_session import ConversationSession
from app.models.document import Topic
from app.repositories.chat_turn_event_repository import ChatTurnEventRepository
from app.repositories.session_repository import SessionRepository


async def _seed_session(session: AsyncSession) -> ConversationSession:
    return await SessionRepository(session).create(
        student_type=None, semester=None, college=None, department=None
    )


async def test_count_turns_and_topic_distribution(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repo = ChatTurnEventRepository(session)
        conversation = await _seed_session(session)

        await repo.create(
            session_id=conversation.id,
            intent=ChatTurnIntent.QUESTION,
            topic=Topic.HOUSING,
            needs_clarification=False,
            grounded=True,
            citation_count=2,
            latency_ms=120.0,
        )
        await repo.create(
            session_id=conversation.id,
            intent=ChatTurnIntent.QUESTION,
            topic=Topic.HOUSING,
            needs_clarification=False,
            grounded=False,
            citation_count=0,
            latency_ms=340.0,
        )
        await repo.create(
            session_id=conversation.id,
            intent=ChatTurnIntent.QUESTION,
            topic=Topic.FINANCIAL_AID,
            needs_clarification=True,
            grounded=None,
            citation_count=0,
            latency_ms=80.0,
        )
        await repo.create(
            session_id=conversation.id,
            intent=ChatTurnIntent.GREETING,
            topic=None,
            needs_clarification=False,
            grounded=None,
            citation_count=0,
            latency_ms=10.0,
        )

        assert await repo.count_turns() == 4

        # grounded_rate only considers QUESTION-intent turns (the greeting
        # row is excluded regardless of its own grounded value): of the 3
        # question turns, 1 True + 2 False/None -> 1/3.
        assert await repo.grounded_rate() == pytest.approx(1 / 3)

        # clarification_rate is over every turn: 1 of 4 -> 0.25.
        assert await repo.clarification_rate() == 0.25

        distribution = dict(await repo.topic_distribution())
        assert distribution == {Topic.HOUSING: 2, Topic.FINANCIAL_AID: 1}

        avg_ms, p50_ms, p95_ms = await repo.latency_stats()
        assert avg_ms is not None
        assert p50_ms is not None
        assert p95_ms is not None


async def test_empty_table_returns_none_not_zero(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repo = ChatTurnEventRepository(session)

        assert await repo.count_turns() == 0
        assert await repo.grounded_rate() is None
        assert await repo.clarification_rate() is None
        assert await repo.topic_distribution() == []

        avg_ms, p50_ms, p95_ms = await repo.latency_stats()
        assert avg_ms is None
        assert p50_ms is None
        assert p95_ms is None


async def test_since_filter_excludes_older_rows(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repo = ChatTurnEventRepository(session)
        conversation = await _seed_session(session)
        await repo.create(
            session_id=conversation.id,
            intent=ChatTurnIntent.QUESTION,
            topic=Topic.HOUSING,
            needs_clarification=False,
            grounded=True,
            citation_count=1,
            latency_ms=100.0,
        )

        # Naive, matching created_at's own naive-DateTime column (populated
        # by Postgres's func.now()) -- see app/api/analytics.py's identical
        # comment on the same tz-aware-vs-naive asyncpg mismatch.
        future_cutoff = (datetime.now(UTC) + timedelta(days=1)).replace(tzinfo=None)
        assert await repo.count_turns(since=future_cutoff) == 0
        assert await repo.count_turns(since=None) == 1
