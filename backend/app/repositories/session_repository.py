import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import ConversationSession, StudentType


class SessionRepository:
    """Data access for ConversationSession. No query logic belongs above this layer."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        student_type: StudentType | None,
        semester: str | None,
        college: str | None,
        department: str | None,
    ) -> ConversationSession:
        session = ConversationSession(
            student_type=student_type,
            semester=semester,
            college=college,
            department=department,
        )
        self._db.add(session)
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> ConversationSession | None:
        return await self._db.get(ConversationSession, session_id)

    async def update_student_type(
        self, session_id: uuid.UUID, student_type: StudentType
    ) -> ConversationSession | None:
        session = await self.get_by_id(session_id)
        if session is None:
            return None
        session.student_type = student_type
        await self._db.commit()
        await self._db.refresh(session)
        return session

    async def count_sessions(self, *, since: datetime | None = None) -> int:
        query = select(func.count()).select_from(ConversationSession)
        if since is not None:
            query = query.where(ConversationSession.created_at >= since)
        result = await self._db.execute(query)
        return result.scalar_one()
