from fastapi import APIRouter, Query

from app.api.dependencies import HybridRetrieverDep
from app.models.conversation_session import StudentType
from app.models.document import Topic
from app.schemas.retrieval import RetrievalDebugResponse, RetrievedChunkResponse

router = APIRouter(prefix="/retrieve", tags=["retrieval-debugging"])


@router.get("", response_model=RetrievalDebugResponse)
async def debug_retrieve(
    retriever: HybridRetrieverDep,
    query: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    topic: Topic | None = None,
    student_type: StudentType | None = None,
) -> RetrievalDebugResponse:
    """Exposes raw hybrid-search results with per-ranker scores, for
    inspecting retrieval quality independent of the (later) LLM generation
    step -- the "Retrieval Debugging" surface called for in the spec."""
    results = await retriever.search(query, limit=limit, topic=topic, student_type=student_type)
    return RetrievalDebugResponse(
        query=query,
        results=[RetrievedChunkResponse.model_validate(r, from_attributes=True) for r in results],
    )
