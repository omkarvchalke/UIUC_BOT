import uuid
from dataclasses import dataclass
from typing import Literal

from app.core.logging import get_logger
from app.embeddings.embedder import Embedder
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository

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
    """Embeds each document's chunks and writes them onto
    DocumentChunk.embedding (pgvector).

    Idempotent the same way IngestionService is: embedded_content_hash is
    compared against content_hash, so re-running only does work for
    documents that actually changed (or were never indexed). No separate
    vector-store client needed here anymore -- embeddings live in the same
    Postgres row as the chunk they belong to (see DocumentRepository.
    set_chunk_embeddings), so "indexing" is just filling in a column.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        *,
        embedder: Embedder | None = None,
    ) -> None:
        self._documents = document_repository
        self._embedder = embedder or Embedder()

    async def index_all(self) -> list[IndexResult]:
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

        await self._documents.set_chunk_embeddings(document.chunks, vectors)
        await self._documents.mark_indexed(document.id, document.content_hash)

        logger.info("indexing_document_indexed", url=document.url, chunk_count=len(vectors))
        return IndexResult(document.id, document.url, "indexed", chunk_count=len(vectors))
