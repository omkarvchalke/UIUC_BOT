import uuid

from app.core.exceptions import SessionNotFoundError
from app.models.conversation_session import ConversationSession, StudentType
from app.repositories.session_repository import SessionRepository


class SessionService:
    """Business logic for anonymous student sessions. Routes never touch the repository directly."""

    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    async def create_session(
        self,
        *,
        student_type: StudentType | None,
        semester: str | None,
        college: str | None,
        department: str | None,
    ) -> ConversationSession:
        return await self._repository.create(
            student_type=student_type,
            semester=semester.strip() if semester else None,
            college=college.strip() if college else None,
            department=department.strip() if department else None,
        )

    async def get_session(self, session_id: uuid.UUID) -> ConversationSession:
        session = await self._repository.get_by_id(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    async def update_student_type(
        self, session_id: uuid.UUID, student_type: StudentType
    ) -> ConversationSession:
        session = await self._repository.update_student_type(session_id, student_type)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session
