import uuid

from app.core.exceptions import DocumentNotFoundError
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository


class DocumentService:
    def __init__(self, repository: DocumentRepository) -> None:
        self._repository = repository

    async def list_documents(self, *, limit: int, offset: int) -> tuple[list[Document], int]:
        documents = await self._repository.list_documents(limit=limit, offset=offset)
        total = await self._repository.count_documents()
        return documents, total

    async def get_document(self, document_id: uuid.UUID) -> Document:
        document = await self._repository.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        return document
