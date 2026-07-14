from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.repositories.session_repository import SessionRepository
from app.services.session_service import SessionService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_session_repository(db: DbSession) -> SessionRepository:
    return SessionRepository(db)


SessionRepositoryDep = Annotated[SessionRepository, Depends(get_session_repository)]


def get_session_service(repository: SessionRepositoryDep) -> SessionService:
    return SessionService(repository)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
