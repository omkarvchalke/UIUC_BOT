from fastapi import APIRouter, Query, Request

from app.api.dependencies import HybridRetrieverDep
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.models.conversation_session import StudentType
from app.models.document import Audience, DocumentType, Topic
from app.schemas.retrieval import RetrievalDebugResponse, RetrievedChunkResponse

router = APIRouter(prefix="/retrieve", tags=["retrieval-debugging"])


@router.get("", response_model=RetrievalDebugResponse)
@limiter.limit(lambda: get_settings().retrieve_rate_limit)
async def debug_retrieve(
    request: Request,
    retriever: HybridRetrieverDep,
    query: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    topic: Topic | None = None,
    student_type: StudentType | None = None,
    audience: Audience | None = None,
    document_type: DocumentType | None = None,
) -> RetrievalDebugResponse:
    """Exposes raw hybrid-search results with per-ranker scores, for
    inspecting retrieval quality independent of the (later) LLM generation
    step -- the "Retrieval Debugging" surface called for in the spec.

    audience/document_type are debug-only knobs for now: no graph node
    derives them from a real conversation signal yet (only student_type
    is collected from the user) -- see app/graph/nodes.py's metadata_filter
    node. Exposed here so the underlying filtering (see
    VectorRepository._build_filter / HybridRetriever._filter_corpus) can
    be hand-verified without any graph/UI change.
    """
    results = await retriever.search(
        query,
        limit=limit,
        topic=topic,
        student_type=student_type,
        audience=audience,
        document_type=document_type,
    )
    return RetrievalDebugResponse(
        query=query,
        results=[RetrievedChunkResponse.model_validate(r, from_attributes=True) for r in results],
    )
