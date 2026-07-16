import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_turn_event import ChatTurnEvent, ChatTurnIntent
from app.models.document import Topic


class ChatTurnEventRepository:
    """Data access for ChatTurnEvent. No query logic belongs above this layer.

    Every aggregate below is a real SQL GROUP BY/COUNT/AVG/percentile_cont,
    not a fetch-then-sum-in-Python -- correct at any table size, and
    consistent with DocumentRepository.count_documents()'s own
    select(func.count()) pattern.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        session_id: uuid.UUID,
        intent: ChatTurnIntent,
        topic: Topic | None,
        needs_clarification: bool,
        grounded: bool | None,
        citation_count: int,
        latency_ms: float | None,
    ) -> ChatTurnEvent:
        event = ChatTurnEvent(
            session_id=session_id,
            intent=intent,
            topic=topic,
            needs_clarification=needs_clarification,
            grounded=grounded,
            citation_count=citation_count,
            latency_ms=latency_ms,
        )
        self._db.add(event)
        await self._db.commit()
        await self._db.refresh(event)
        return event

    @staticmethod
    def _since(query: Select[Any], since: datetime | None) -> Select[Any]:
        if since is None:
            return query
        return query.where(ChatTurnEvent.created_at >= since)

    async def count_turns(self, *, since: datetime | None = None) -> int:
        query = self._since(select(func.count()).select_from(ChatTurnEvent), since)
        result = await self._db.execute(query)
        return int(result.scalar_one())

    async def list_by_session(self, session_id: uuid.UUID) -> list[ChatTurnEvent]:
        query = select(ChatTurnEvent).where(ChatTurnEvent.session_id == session_id)
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def grounded_rate(self, *, since: datetime | None = None) -> float | None:
        # Only over question turns, not "grounded is not None": greeting_
        # answer() (app/graph/generation.py) always sets grounded=True for
        # greeting turns too (a canned answer is trivially "grounded" in
        # itself), so including them here would inflate the rate with
        # turns that never answered a real question at all.
        query = self._since(
            select(func.avg(case((ChatTurnEvent.grounded.is_(True), 1.0), else_=0.0))).where(
                ChatTurnEvent.intent == ChatTurnIntent.QUESTION
            ),
            since,
        )
        result = await self._db.execute(query)
        rate = result.scalar_one()
        return float(rate) if rate is not None else None

    async def clarification_rate(self, *, since: datetime | None = None) -> float | None:
        query = self._since(
            select(func.avg(case((ChatTurnEvent.needs_clarification.is_(True), 1.0), else_=0.0))),
            since,
        )
        result = await self._db.execute(query)
        rate = result.scalar_one()
        return float(rate) if rate is not None else None

    async def topic_distribution(self, *, since: datetime | None = None) -> list[tuple[Topic, int]]:
        query = self._since(
            select(ChatTurnEvent.topic, func.count())
            .where(ChatTurnEvent.topic.is_not(None))
            .group_by(ChatTurnEvent.topic)
            .order_by(func.count().desc()),
            since,
        )
        result = await self._db.execute(query)
        return [(topic, count) for topic, count in result.all() if topic is not None]

    async def latency_stats(
        self, *, since: datetime | None = None
    ) -> tuple[float | None, float | None, float | None]:
        query = self._since(
            select(
                func.avg(ChatTurnEvent.latency_ms),
                func.percentile_cont(0.5).within_group(ChatTurnEvent.latency_ms),
                func.percentile_cont(0.95).within_group(ChatTurnEvent.latency_ms),
            ).where(ChatTurnEvent.latency_ms.is_not(None)),
            since,
        )
        result = await self._db.execute(query)
        avg_ms, p50_ms, p95_ms = result.one()
        return avg_ms, p50_ms, p95_ms
