import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.ingestion.chunk_identity import compute_chunk_id
from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import (
    Audience,
    Document,
    DocumentChunk,
    DocumentType,
    DocumentVersion,
    IndexStatus,
    SourceRole,
    SourceType,
    Topic,
)
from app.retrieval.priority import compute_authority_score, compute_retrieval_priority


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_url(self, url: str) -> Document | None:
        result = await self._db.execute(select(Document).where(Document.url == url))
        return result.scalar_one_or_none()

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        result = await self._db.execute(
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chunks))
        )
        return result.scalar_one_or_none()

    async def list_documents(self, *, limit: int, offset: int) -> list[Document]:
        result = await self._db.execute(
            select(Document)
            .order_by(Document.department, Document.title)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_documents(self) -> int:
        result = await self._db.execute(select(func.count()).select_from(Document))
        return result.scalar_one()

    async def upsert_document(
        self,
        *,
        url: str,
        title: str,
        department: str,
        topic: Topic,
        source_type: SourceType,
        student_types: tuple[StudentType, ...],
        last_updated: datetime | None,
        content_hash: str,
        audience: tuple[Audience, ...] = (),
        document_type: DocumentType | None = None,
        keywords: tuple[str, ...] = (),
        last_crawled_at: datetime | None = None,
        subtopic: str | None = None,
        source_role: SourceRole | None = None,
        http_status: int | None = None,
        word_count: int | None = None,
    ) -> Document:
        # authority_score/retrieval_priority are always (re-)computed here, never passed in --
        # see app/retrieval/priority.py's module docstring for why they're derived rather than
        # accepted as raw input. retrieval_priority depends on temporal_scope, which isn't part
        # of the normal ingestion flow (set separately -- see scripts/remap_topics_v2.py), so a
        # new document computes it with temporal_scope=None (the same as "unspecified") and an
        # existing document keeps whatever temporal_scope it already has.
        authority_score = compute_authority_score(source_type)
        document = await self.get_by_url(url)
        if document is None:
            document = Document(
                url=url,
                title=title,
                department=department,
                topic=topic,
                subtopic=subtopic,
                source_type=source_type,
                source_role=source_role,
                student_types=list(student_types),
                audience=list(audience),
                document_type=document_type,
                keywords=list(keywords),
                last_updated=last_updated,
                last_crawled_at=last_crawled_at,
                content_hash=content_hash,
                authority_score=authority_score,
                retrieval_priority=compute_retrieval_priority(source_role, None),
                index_status=IndexStatus.APPROVED,
                http_status=http_status,
                word_count=word_count,
            )
            self._db.add(document)
        else:
            # Write a version row capturing the *previous* content before
            # overwriting -- only when the content actually changed, so a
            # document that's re-ingested unchanged (the common case)
            # never accumulates version rows. This is an audit trail, not
            # a duplicate of current content: it's written pre-overwrite,
            # so it always lags one step behind Document itself.
            if document.content_hash != content_hash:
                self._db.add(
                    DocumentVersion(
                        document_id=document.id,
                        content_hash=document.content_hash,
                        title=document.title,
                    )
                )
            # embedded_content_hash is what IndexingService compares against
            # content_hash to decide whether this document needs
            # re-embedding (see app/models/document.py). Only content_hash
            # matters here: unlike when Qdrant held a denormalized payload
            # copy of topic/department/student_types/audience/document_type
            # (requiring a re-index on any metadata change to avoid serving
            # a stale filter value), VectorRepository now joins straight
            # against this Document row on every search -- a metadata-only
            # change (topic corrected, content unchanged) is live the
            # instant this commits, no re-embedding required.
            if document.content_hash != content_hash:
                document.embedded_content_hash = None
            document.title = title
            document.department = department
            document.topic = topic
            document.subtopic = subtopic
            document.source_type = source_type
            document.source_role = source_role
            document.student_types = list(student_types)
            document.audience = list(audience)
            document.document_type = document_type
            document.keywords = list(keywords)
            document.last_updated = last_updated
            document.last_crawled_at = last_crawled_at
            document.content_hash = content_hash
            document.authority_score = authority_score
            document.retrieval_priority = compute_retrieval_priority(
                source_role, document.temporal_scope
            )
            # index_status is deliberately NOT reset here -- a human may have manually blocked
            # or flagged this document for review (Source Manifest V2, Part 7), and a routine
            # re-crawl must not silently un-block it. Only scripts/remap_topics_v2.py or a
            # future moderation tool should change index_status on an existing document.
            document.http_status = http_status
            document.word_count = word_count

        await self._db.flush()
        await self._db.refresh(document)
        return document

    async def touch_last_crawled(self, document_id: uuid.UUID) -> None:
        """Records that a document's URL was just checked, without any
        content change -- used by the unchanged-content skip path in
        IngestionService and by incremental crawling (scripts/run_crawl.py
        --incremental) to know which URLs are due for a recheck."""
        document = await self.get_by_id(document_id)
        if document is None:
            return
        document.last_crawled_at = datetime.now(UTC)
        await self._db.commit()

    async def list_versions(self, document_id: uuid.UUID) -> list[DocumentVersion]:
        result = await self._db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.captured_at)
        )
        return list(result.scalars().all())

    async def replace_chunks(self, document_id: uuid.UUID, chunks: list[ChunkResult]) -> None:
        await self._db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        # local_index (0-based position within this chunk's own section, for compute_chunk_id)
        # tracked separately from `number` (1-based across the whole document, unchanged
        # meaning) -- resets to 0 every time section_index changes.
        local_index = 0
        previous_section_index: int | None = None
        for number, chunk in enumerate(chunks, start=1):
            if chunk.section_index != previous_section_index:
                local_index = 0
                previous_section_index = chunk.section_index
            self._db.add(
                DocumentChunk(
                    id=compute_chunk_id(
                        document_id,
                        section_index=chunk.section_index,
                        local_index=local_index,
                        content=chunk.text,
                    ),
                    document_id=document_id,
                    chunk_number=number,
                    content=chunk.text,
                    char_count=len(chunk.text),
                    subtopic=chunk.subtopic,
                    section_index=chunk.section_index,
                    parent_text=chunk.parent_text,
                )
            )
            local_index += 1
        await self._db.commit()

    async def list_documents_needing_index(self) -> list[Document]:
        result = await self._db.execute(
            select(Document)
            .where(
                Document.embedded_content_hash.is_(None)
                | (Document.embedded_content_hash != Document.content_hash)
            )
            .options(selectinload(Document.chunks))
        )
        return list(result.scalars().all())

    async def mark_indexed(
        self, document_id: uuid.UUID, content_hash: str, *, embedding_version: str | None = None
    ) -> None:
        document = await self.get_by_id(document_id)
        if document is None:
            return
        document.embedded_content_hash = content_hash
        if embedding_version is not None:
            document.embedding_version = embedding_version
        await self._db.commit()

    async def set_chunk_embeddings(
        self, chunks: list[DocumentChunk], vectors: list[list[float]]
    ) -> None:
        # Embeddings live on DocumentChunk itself (pgvector), not a separate
        # store, so "indexing" a document is just filling in a column on
        # rows IngestionService already wrote via replace_chunks -- no
        # delete-then-reinsert needed the way a separate vector store
        # required.
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk.embedding = vector
        await self._db.commit()

    async def list_all_chunks_with_documents(self) -> list[DocumentChunk]:
        result = await self._db.execute(
            select(DocumentChunk).options(joinedload(DocumentChunk.document))
        )
        return list(result.scalars().all())
