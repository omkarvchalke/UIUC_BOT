import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation_session import StudentType
from app.models.document import Document, DocumentChunk, SourceType, Topic


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
                last_updated=last_updated,
                content_hash=content_hash,
            )
            self._db.add(document)
        else:
            document.title = title
            document.department = department
            document.topic = topic
            document.source_type = source_type
            document.student_types = list(student_types)
            document.last_updated = last_updated
            document.content_hash = content_hash

        await self._db.flush()
        await self._db.refresh(document)
        return document

    async def replace_chunks(self, document_id: uuid.UUID, chunk_texts: list[str]) -> None:
        await self._db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )
        for number, text in enumerate(chunk_texts, start=1):
            self._db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_number=number,
                    content=text,
                    char_count=len(text),
                )
            )
        await self._db.commit()
