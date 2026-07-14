import uuid

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import DocumentServiceDep
from app.core.exceptions import DocumentNotFoundError
from app.schemas.document import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> DocumentListResponse:
    documents, total = await service.list_documents(limit=limit, offset=offset)
    return DocumentListResponse(
        total=total,
        limit=limit,
        offset=offset,
        documents=[DocumentSummaryResponse.model_validate(doc) for doc in documents],
    )


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: uuid.UUID, service: DocumentServiceDep
) -> DocumentDetailResponse:
    try:
        document = await service.get_document(document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return DocumentDetailResponse.model_validate(document)
