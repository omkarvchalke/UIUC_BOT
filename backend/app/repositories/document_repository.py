import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import (
    Audience,
    Document,
    DocumentChunk,
    DocumentType,
    DocumentVersion,
    SourceType,
    Topic,
)


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
    ) -> Document:
        document = await self.get_by_url(url)
        if document is None:
            document = Document(
                url=url,
                title=title,
                department=department,
                topic=topic,
                source_type=source_type,
                student_types=list(student_types),
                audience=list(audience),
                document_type=document_type,
                keywords=list(keywords),
                last_updated=last_updated,
                last_crawled_at=last_crawled_at,
                content_hash=content_hash,
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
            document.title = title
            document.department = department
            document.topic = topic
            document.source_type = source_type
            document.student_types = list(student_types)
            document.audience = list(audience)
            document.document_type = document_type
            document.keywords = list(keywords)
            document.last_updated = last_updated
            document.last_crawled_at = last_crawled_at
            document.content_hash = content_hash

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
        for number, chunk in enumerate(chunks, start=1):
            self._db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_number=number,
                    content=chunk.text,
                    char_count=len(chunk.text),
                    subtopic=chunk.subtopic,
                )
            )
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

    async def mark_indexed(self, document_id: uuid.UUID, content_hash: str) -> None:
        document = await self.get_by_id(document_id)
        if document is None:
            return
        document.embedded_content_hash = content_hash
        await self._db.commit()

    async def list_all_chunks_with_documents(self) -> list[DocumentChunk]:
        result = await self._db.execute(
            select(DocumentChunk).options(joinedload(DocumentChunk.document))
        )
        return list(result.scalars().all())
