import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import Topic
from app.models.feedback import FeedbackRating
from app.schemas.chat import ChatCitation


class FeedbackCreateRequest(BaseModel):
    session_id: uuid.UUID
    message_id: str = Field(..., min_length=1, max_length=128)
    question: str = Field(..., min_length=1, max_length=2000)
    answer: str = Field(..., min_length=1, max_length=8000)
    rating: FeedbackRating
    comment: str | None = Field(default=None, max_length=2000)
    # Both optional/nullable so older frontend builds that don't send them
    # yet keep working -- see Feedback.topic/.citations for why these are
    # snapshotted from the frontend rather than looked up server-side.
    topic: Topic | None = None
    citations: list[ChatCitation] | None = None


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    message_id: str
    rating: FeedbackRating
    created_at: datetime
