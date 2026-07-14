import uuid
from dataclasses import dataclass

from app.core.logging import get_logger
from app.embeddings.embedder import Embedder
from app.models.conversation_session import StudentType
from app.models.document import DocumentChunk, SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.bm25_search import BM25Search

logger = get_logger(__name__)

# Standard constant from the original Reciprocal Rank Fusion paper (Cormack
# et al.). Large enough that rank 1 vs. rank 2 doesn't dominate the fused
# score, so a chunk ranked decently by *both* rankers can outscore a chunk
# ranked #1 by only one of them.
_RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    chunk_number: int
    url: str
    title: str
    department: str
    topic: Topic
    source_type: SourceType
    fused_score: float
    semantic_rank: int | None
    bm25_rank: int | None


class HybridRetriever:
    """Combines Qdrant semantic search with in-process BM25 keyword search
    via Reciprocal Rank Fusion.

    RRF over rank position (not raw score averaging) sidesteps the fact that
    cosine similarity and BM25 scores live on entirely different, incomparable
    scales -- there's no principled way to weight-average them directly, but
    "how many results did this beat" is comparable across any two rankers.

    Metadata for results always comes from the Postgres corpus fetched for
    BM25, never from Qdrant's payload -- Postgres stays the single source of
    truth for document metadata; Qdrant is purely a similarity ranker here.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        vector_repository: VectorRepository,
        *,
        embedder: Embedder | None = None,
    ) -> None:
        self._documents = document_repository
        self._vectors = vector_repository
        self._embedder = embedder or Embedder()
        self._corpus_cache: dict[tuple[Topic | None, StudentType | None], list[DocumentChunk]] = {}

    async def search(
        self,
        query: str,
        *,
        limit: int = 5,
        candidate_limit: int = 20,
        topic: Topic | None = None,
        student_type: StudentType | None = None,
    ) -> list[RetrievedChunk]:
        query_vector = self._embedder.embed_query(query)

        semantic_points = await self._vectors.search(
            query_vector, limit=candidate_limit, topic=topic, student_type=student_type
        )
        corpus = await self._get_corpus(topic=topic, student_type=student_type)
        bm25_results = BM25Search(corpus).search(query, limit=candidate_limit)

        corpus_by_id = {str(chunk.id): chunk for chunk in corpus}
        semantic_ranks = {
            str(point.id): rank for rank, point in enumerate(semantic_points, start=1)
        }
        bm25_ranks = {
            str(result.chunk.id): rank for rank, result in enumerate(bm25_results, start=1)
        }

        return self._fuse(corpus_by_id, semantic_ranks, bm25_ranks, limit=limit)

    async def _get_corpus(
        self, *, topic: Topic | None, student_type: StudentType | None
    ) -> list[DocumentChunk]:
        # Cached per (topic, student_type) combination for the lifetime of
        # this retriever instance (one request via DI) -- rebuilding per
        # call would mean re-fetching the whole matching corpus from
        # Postgres on every graph node that calls search().
        cache_key = (topic, student_type)
        if cache_key not in self._corpus_cache:
            chunks = await self._documents.list_all_chunks_with_documents()
            if topic is not None:
                chunks = [chunk for chunk in chunks if chunk.document.topic is topic]
            if student_type is not None:
                chunks = [
                    chunk
                    for chunk in chunks
                    if not chunk.document.student_types
                    or student_type in chunk.document.student_types
                ]
            self._corpus_cache[cache_key] = chunks
        return self._corpus_cache[cache_key]

    @staticmethod
    def _fuse(
        corpus_by_id: dict[str, DocumentChunk],
        semantic_ranks: dict[str, int],
        bm25_ranks: dict[str, int],
        *,
        limit: int,
    ) -> list[RetrievedChunk]:
        all_ids = set(semantic_ranks) | set(bm25_ranks)

        scored: list[tuple[str, float]] = []
        for chunk_id in all_ids:
            score = 0.0
            if chunk_id in semantic_ranks:
                score += 1 / (_RRF_K + semantic_ranks[chunk_id])
            if chunk_id in bm25_ranks:
                score += 1 / (_RRF_K + bm25_ranks[chunk_id])
            scored.append((chunk_id, score))

        scored.sort(key=lambda pair: pair[1], reverse=True)

        results = []
        for chunk_id, score in scored[:limit]:
            chunk = corpus_by_id.get(chunk_id)
            if chunk is None:
                # Qdrant returned a point whose chunk no longer exists in
                # Postgres (e.g. index lagging a deletion) -- drop it rather
                # than surface a citation to content that no longer exists.
                logger.warning("hybrid_search_stale_point", chunk_id=chunk_id)
                continue
            document = chunk.document
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    content=chunk.content,
                    chunk_number=chunk.chunk_number,
                    url=document.url,
                    title=document.title,
                    department=document.department,
                    topic=document.topic,
                    source_type=document.source_type,
                    fused_score=score,
                    semantic_rank=semantic_ranks.get(chunk_id),
                    bm25_rank=bm25_ranks.get(chunk_id),
                )
            )
        return results
