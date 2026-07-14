import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    chunk_number: int
    content: str
    char_count: int


class DocumentSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    url: str
    title: str
    department: str
    topic: Topic
    source_type: SourceType
    student_types: list[StudentType]
    last_updated: datetime | None
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentSummaryResponse):
    chunks: list[DocumentChunkResponse]


class DocumentListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    documents: list[DocumentSummaryResponse]
