import uuid

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
