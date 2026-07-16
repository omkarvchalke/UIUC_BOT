import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base
from app.models.document import Topic, _string_backed_enum


class ChatTurnIntent(enum.StrEnum):
    GREETING = "greeting"
    QUESTION = "question"


_chat_turn_intent_enum = SAEnum(
    ChatTurnIntent,
    name="chat_turn_intent",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class ChatTurnEvent(Base):
    """One row per completed chat turn -- the same fields
    save_conversation_state (app/graph/nodes.py) has always computed and
    logged as a "graph_turn_complete" structured log line, now also
    persisted so they're queryable (topic distribution, grounded rate,
    clarification rate, latency) instead of living only in log output.

    Written from the API layer (app/api/chat.py), not from inside the
    graph -- the graph's job stays conversation orchestration, and the
    route is the only place that can measure true end-to-end latency
    around graph.ainvoke().
    """

    __tablename__ = "chat_turn_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversation_sessions.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    intent: Mapped[ChatTurnIntent] = mapped_column(_chat_turn_intent_enum)
    # Reuses Document.topic's own column helper -- same VARCHAR-backed,
    # migration-free-to-extend pattern, since this stores the exact same
    # Topic values. Nullable: greeting turns never classify a topic.
    topic: Mapped[Topic | None] = mapped_column(_string_backed_enum(Topic, length=64))
    needs_clarification: Mapped[bool] = mapped_column(default=False)
    # Nullable for defensive/forward-compat reasons (a schema shouldn't
    # assume every future code path populates this), though in practice
    # every turn today sets a real value: greeting_answer() (generation.py)
    # returns grounded=True unconditionally for greetings, so
    # ChatTurnEventRepository.grounded_rate() filters by intent=="question",
    # not "grounded is not None", to avoid trivially-true greeting turns
    # inflating the rate.
    grounded: Mapped[bool | None] = mapped_column()
    citation_count: Mapped[int] = mapped_column(default=0)
    # Nullable only so the schema doesn't need to change if a future
    # writer can't measure it -- the one writer this phase adds always
    # populates it.
    latency_ms: Mapped[float | None] = mapped_column()
