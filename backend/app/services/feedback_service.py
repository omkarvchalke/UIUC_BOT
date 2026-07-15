import uuid

from app.core.exceptions import SessionNotFoundError
from app.models.feedback import Feedback, FeedbackRating
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.session_repository import SessionRepository


class FeedbackService:
    """Business logic for answer feedback. Routes never touch the repository directly."""

    def __init__(
        self, repository: FeedbackRepository, session_repository: SessionRepository
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository

    async def submit_feedback(
        self,
        *,
        session_id: uuid.UUID,
        message_id: str,
        question: str,
        answer: str,
        rating: FeedbackRating,
        comment: str | None,
    ) -> Feedback:
        # Checked explicitly rather than letting a bad session_id surface
        # as a raw FK IntegrityError from the DB -- same pattern as
        # SessionService.get_session.
        session = await self._session_repository.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)

        return await self._repository.create(
            session_id=session_id,
            message_id=message_id.strip(),
            question=question.strip(),
            answer=answer.strip(),
            rating=rating,
            comment=comment.strip() if comment else None,
        )
