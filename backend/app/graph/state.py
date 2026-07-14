from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from app.models.conversation_session import StudentType
from app.models.document import Topic

Intent = Literal["greeting", "question"]
ClarificationReason = Literal["missing_profile", "ambiguous_topic"]


class RetrievedChunkState(TypedDict):
    chunk_id: str
    document_id: str
    content: str
    title: str
    url: str
    department: str
    topic: str
    fused_score: float
    rerank_score: NotRequired[float]


class CitationState(TypedDict):
    title: str
    url: str
    department: str
    topic: str


class GraphState(TypedDict):
    """Typed state threaded through every node.

    Only `session_id` and `messages` are required to start a turn; every
    other field is populated progressively as nodes run, which is why
    they're NotRequired (LangGraph merges each node's partial-dict return
    into this accumulated state rather than requiring nodes to restate
    everything). `messages` uses the `add_messages` reducer so it
    *appends* across turns instead of being overwritten -- that, plus the
    Postgres checkpointer the graph is compiled with, is what makes
    conversation memory durable across a session's turns without a
    dedicated "message history" table of our own.
    """

    session_id: str
    messages: Annotated[list[BaseMessage], add_messages]

    # Student profile -- non-PII, mirrors ConversationSession (Phase 2).
    # Loaded from Postgres each turn (load_session node) so it survives
    # process restarts even though `messages` history for a *new* checkpointer
    # backend would not.
    student_type: NotRequired[StudentType | None]
    semester: NotRequired[str | None]
    college: NotRequired[str | None]
    department: NotRequired[str | None]
    profile_asked: NotRequired[bool]

    # Routing signals set by intent_detection / question_classification.
    intent: NotRequired[Intent]
    topic: NotRequired[Topic | None]
    classification_confidence: NotRequired[float]
    needs_clarification: NotRequired[bool]
    clarification_reason: NotRequired[ClarificationReason | None]

    # Retrieval pipeline outputs.
    retrieved_chunks: NotRequired[list[RetrievedChunkState]]
    reranked_chunks: NotRequired[list[RetrievedChunkState]]
    context: NotRequired[str]

    # Generation outputs.
    answer: NotRequired[str]
    citations: NotRequired[list[CitationState]]
    grounded: NotRequired[bool]
