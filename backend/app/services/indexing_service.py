import uuid
from dataclasses import dataclass
from typing import Literal

from qdrant_client import models

from app.core.logging import get_logger
from app.embeddings.embedder import Embedder
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository

logger = get_logger(__name__)

IndexStatus = Literal["indexed", "skipped", "failed"]


@dataclass(frozen=True)
class IndexResult:
    document_id: uuid.UUID
    url: str
    status: IndexStatus
    chunk_count: int = 0
    error: str | None = None


class IndexingService:
    """Embeds each document's chunks and upserts them into Qdrant.

    Idempotent the same way IngestionService is: embedded_content_hash is
    compared against content_hash, so re-running only does work for
    documents that actually changed (or were never indexed).
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

    async def index_all(self) -> list[IndexResult]:
        await self._vectors.ensure_collection()
        documents = await self._documents.list_documents_needing_index()
        return [await self.index_document(document) for document in documents]

    async def index_document(self, document: Document) -> IndexResult:
        if document.embedded_content_hash == document.content_hash:
            return IndexResult(document.id, document.url, "skipped")

        if not document.chunks:
            logger.warning("indexing_no_chunks", url=document.url)
            return IndexResult(document.id, document.url, "failed", error="document has no chunks")

        try:
            vectors = self._embedder.embed_documents([chunk.content for chunk in document.chunks])
        except Exception as exc:  # noqa: BLE001 - one bad document must not abort the batch
            logger.warning("indexing_embed_failed", url=document.url, error=str(exc))
            return IndexResult(document.id, document.url, "failed", error=str(exc))

        # Delete-then-insert by document_id rather than tracking individual
        # old point IDs: simpler, and correct even if chunk count changed
        # (fewer/more chunks than the previous version) or the document was
        # never indexed before (delete of a non-existent filter is a no-op).
        await self._vectors.delete_by_document_id(document.id)

        points = [
            models.PointStruct(
                id=str(chunk.id),
                vector=vector,
                payload={
                    "document_id": str(document.id),
                    "chunk_id": str(chunk.id),
                    "chunk_number": chunk.chunk_number,
                    "content": chunk.content,
                    "url": document.url,
                    "title": document.title,
                    "department": document.department,
                    "topic": document.topic.value,
                    "source_type": document.source_type.value,
                    "student_types": [st.value for st in document.student_types],
                    "audience": [a.value for a in document.audience],
                    "document_type": (
                        document.document_type.value if document.document_type else None
                    ),
                    "subtopic": chunk.subtopic,
                    "last_updated": (
                        document.last_updated.isoformat() if document.last_updated else None
                    ),
                },
            )
            for chunk, vector in zip(document.chunks, vectors, strict=True)
        ]
        await self._vectors.upsert_chunks(points)
        await self._documents.mark_indexed(document.id, document.content_hash)

        logger.info("indexing_document_indexed", url=document.url, chunk_count=len(points))
        return IndexResult(document.id, document.url, "indexed", chunk_count=len(points))
