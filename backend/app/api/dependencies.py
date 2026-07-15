from typing import Annotated

from fastapi import Depends, Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.database.session import get_db_session
from app.graph.dependencies import GraphDependencies
from app.graph.generation import AnswerGenerator, ExtractiveAnswerGenerator
from app.graph.graph import build_graph
from app.graph.state import GraphState
from app.llm.groq_answer_generator import GroqAnswerGenerator
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.topic_classifier import TopicClassifier
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


def get_answer_generator() -> AnswerGenerator:
    # Falls back to the LLM-free placeholder when no Groq key is configured,
    # so local dev and tests work without a real credential -- only the
    # actual chat endpoint needs one.
    if get_settings().groq_api_key:
        return GroqAnswerGenerator()
    return ExtractiveAnswerGenerator()


AnswerGeneratorDep = Annotated[AnswerGenerator, Depends(get_answer_generator)]


def get_graph_dependencies(
    session_service: SessionServiceDep,
    hybrid_retriever: HybridRetrieverDep,
    answer_generator: AnswerGeneratorDep,
) -> GraphDependencies:
    return GraphDependencies(
        session_service=session_service,
        hybrid_retriever=hybrid_retriever,
        topic_classifier=TopicClassifier(),
        reranker=CrossEncoderReranker(),
        answer_generator=answer_generator,
    )


GraphDependenciesDep = Annotated[GraphDependencies, Depends(get_graph_dependencies)]


def get_checkpointer(request: Request) -> BaseCheckpointSaver[str]:
    return request.app.state.checkpointer  # type: ignore[no-any-return]


CheckpointerDep = Annotated[BaseCheckpointSaver[str], Depends(get_checkpointer)]


def get_compiled_graph(
    deps: GraphDependenciesDep, checkpointer: CheckpointerDep
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    return build_graph(deps, checkpointer=checkpointer)


CompiledGraphDep = Annotated[
    CompiledStateGraph[GraphState, None, GraphState, GraphState], Depends(get_compiled_graph)
]
