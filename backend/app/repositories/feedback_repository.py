import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Topic
from app.models.feedback import Feedback, FeedbackRating


class FeedbackRepository:
    """Data access for Feedback. No query logic belongs above this layer."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        session_id: uuid.UUID,
        message_id: str,
        question: str,
        answer: str,
        rating: FeedbackRating,
        comment: str | None,
        topic: Topic | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> Feedback:
        feedback = Feedback(
            session_id=session_id,
            message_id=message_id,
            question=question,
            answer=answer,
            rating=rating,
            comment=comment,
            topic=topic,
            citations=citations,
        )
        self._db.add(feedback)
        await self._db.commit()
        await self._db.refresh(feedback)
        return feedback

    async def count_by_rating(self, *, since: datetime | None = None) -> dict[FeedbackRating, int]:
        query = select(Feedback.rating, func.count()).group_by(Feedback.rating)
        if since is not None:
            query = query.where(Feedback.created_at >= since)
        result = await self._db.execute(query)
        return dict(result.tuples().all())

    async def list_since(self, since: datetime | None) -> list[Feedback]:
        # Used by scripts/tune_retrieval_params.py to pull only feedback
        # newer than the last applied tuning change -- older rows already
        # informed that decision. `since=None` means "no prior applied
        # change exists yet", i.e. consider all-time feedback.
        query = select(Feedback)
        if since is not None:
            query = query.where(Feedback.created_at >= since)
        result = await self._db.execute(query)
        return list(result.scalars().all())
