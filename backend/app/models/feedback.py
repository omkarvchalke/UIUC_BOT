import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base
from app.models.document import Topic, _string_backed_enum


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
    # Nullable: rows from before this column existed have no value and must
    # be treated as "no signal" (not "no topic"/"no citations") by anything
    # reading them, e.g. the retrieval-tuning job (scripts/tune_retrieval_params.py).
    # Snapshotted from the frontend's already-in-hand ChatMessage at feedback
    # time rather than looked up server-side -- there's nowhere server-side
    # to look it up from, same reasoning as message_id above.
    topic: Mapped[Topic | None] = mapped_column(_string_backed_enum(Topic, length=64))
    # Snapshot of ChatCitation objects (app/schemas/chat.py), each including
    # rerank_score -- the one piece of retrieval-quality signal this table
    # otherwise has no way to reconstruct after the fact. JSONB (this
    # codebase's first use of it): a citation list is inherently variable-
    # shape and nothing here ever queries into individual citation fields,
    # so a normalized child table would add join overhead for no benefit.
    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
