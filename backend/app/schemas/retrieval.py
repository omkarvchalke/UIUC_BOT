import uuid

from pydantic import BaseModel

from app.models.document import SourceType, Topic


class RetrievedChunkResponse(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    chunk_number: int
    url: str
    title: str
    department: str
    topic: Topic
    source_type: SourceType
    subtopic: str | None
    fused_score: float
    semantic_rank: int | None
    bm25_rank: int | None


class RetrievalDebugResponse(BaseModel):
    query: str
    results: list[RetrievedChunkResponse]
