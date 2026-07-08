import logging

from fastapi import APIRouter, HTTPException

from app.models.schemas import RetrievedChunk, RetrieveRequest, RetrieveResponse
from app.rag.embeddings import EmbeddingConfigError
from app.rag.retriever import DEFAULT_TOP_K, retrieve

logger = logging.getLogger(__name__)

router = APIRouter(tags=["retrieve"])


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_chunks(request: RetrieveRequest) -> RetrieveResponse:
    """Return the top 5 chunks most relevant to the question, with source metadata.

    Returns an empty results list (not an error) if the vector index hasn't
    been built yet. Returns a 503 with a clear message if OPENAI_API_KEY is
    missing or invalid, since that's a configuration problem, not a bad request.
    """
    try:
        results = retrieve(request.question, top_k=DEFAULT_TOP_K)
    except EmbeddingConfigError as exc:
        logger.error("Retrieval failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RetrieveResponse(results=[RetrievedChunk(**r) for r in results])
