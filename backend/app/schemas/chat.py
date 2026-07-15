import uuid

from pydantic import BaseModel, Field

from app.models.document import Topic


class ChatRequest(BaseModel):
    session_id: uuid.UUID
    message: str = Field(..., min_length=1, max_length=2000)


class ChatCitation(BaseModel):
    title: str
    url: str
    department: str
    topic: Topic


class ChatResponse(BaseModel):
    answer: str
    grounded: bool
    needs_clarification: bool
    citations: list[ChatCitation]
