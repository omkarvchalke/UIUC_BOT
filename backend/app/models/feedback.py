import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class FeedbackRating(enum.StrEnum):
    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


_feedback_rating_enum = SAEnum(
    FeedbackRating,
    name="feedback_rating",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class Feedback(Base):
    """Per-answer feedback (thumbs up/down + optional comment).

    Denormalizes question/answer text rather than referencing a persisted
    message id: conversation turns live in the LangGraph checkpointer
    (app/graph/checkpointer.py), not a separate queryable messages table,
    so there's no stable server-side message id to foreign-key against.
    message_id is the frontend's own client-generated id (see
    frontend/src/types/chat.ts), kept only so a given rendered message can
    be correlated across requests (e.g. detecting a resubmission) --
    not validated against anything server-side.
    """

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_sessions.id"))
    message_id: Mapped[str] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    rating: Mapped[FeedbackRating] = mapped_column(_feedback_rating_enum)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
