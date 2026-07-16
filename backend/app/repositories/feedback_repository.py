import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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
    ) -> Feedback:
        feedback = Feedback(
            session_id=session_id,
            message_id=message_id,
            question=question,
            answer=answer,
            rating=rating,
            comment=comment,
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
