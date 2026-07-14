from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.hybrid_search import HybridRetriever
from app.services.document_service import DocumentService
from app.services.session_service import SessionService

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_session_repository(db: DbSession) -> SessionRepository:
    return SessionRepository(db)


SessionRepositoryDep = Annotated[SessionRepository, Depends(get_session_repository)]


def get_session_service(repository: SessionRepositoryDep) -> SessionService:
    return SessionService(repository)


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]


def get_document_repository(db: DbSession) -> DocumentRepository:
    return DocumentRepository(db)


DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]


def get_document_service(repository: DocumentRepositoryDep) -> DocumentService:
    return DocumentService(repository)


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]


def get_vector_repository() -> VectorRepository:
    return VectorRepository()


VectorRepositoryDep = Annotated[VectorRepository, Depends(get_vector_repository)]


def get_hybrid_retriever(
    document_repository: DocumentRepositoryDep, vector_repository: VectorRepositoryDep
) -> HybridRetriever:
    return HybridRetriever(document_repository, vector_repository)


HybridRetrieverDep = Annotated[HybridRetriever, Depends(get_hybrid_retriever)]
