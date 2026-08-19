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
    subtopic: str | None
    fused_score: float
    rerank_score: NotRequired[float]


class CitationState(TypedDict):
    title: str
    url: str
    department: str
    topic: str
    subtopic: str | None
    fused_score: float
    rerank_score: NotRequired[float]


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
    # Set by check_student_profile when this turn's message is a reply to
    # our own "what kind of student are you?" clarifying question (e.g.
    # "Graduate") rather than a fresh question -- the actual question the
    # user asked is the human message *before* that clarifying question,
    # not this reply. When set, question_classification/retrieve/
    # generate_response use this instead of the literal latest human
    # message. See _effective_query in nodes.py.
    query_override: NotRequired[str | None]

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

    # Set once per turn by decompose_query (runs unconditionally between
    # question_classification and metadata_filter -- see graph.py), before
    # the retrieve<->assess_retrieval_sufficiency cycle below can begin.
    # Always a non-empty list: the original question as a single-item list
    # when query decomposition is off/NoOpQueryDecomposer, or 2-3
    # independent sub-questions when it split a genuinely compound one.
    # Unlike reformulated_query/retrieval_attempt below, this needs no
    # separate per-turn reset in metadata_filter -- decompose_query is the
    # sole node on every path into metadata_filter and always overwrites
    # this fresh each turn, same "no reset needed" reasoning
    # retrieval_sufficient's own comment below describes. See
    # _retrieval_queries in nodes.py.
    sub_queries: NotRequired[list[str]]

    # Agentic retrieval loop (assess_retrieval_sufficiency <-> retrieve,
    # see app/graph/edges.py::route_after_sufficiency_check). Deliberately
    # separate from query_override above, not reused: query_override
    # recovers the user's *real* question after a bare profile reply and
    # is read by generate_response too, while reformulated_query is an
    # internal search-string refinement that must steer retrieval only --
    # generate_response and question_classification never read it, so the
    # final answer always addresses what the user actually asked
    # regardless of how retrieval got there. Both fields are explicitly
    # reset to None/0 every turn by metadata_filter (the sole node on the
    # path to retrieve, run once per turn before this cycle can start) --
    # the same stale-state discipline query_override's own docstring
    # describes; a previous turn's leftover value must never leak into
    # this turn's first retrieve() call.
    reformulated_query: NotRequired[str | None]
    # How many retrieve() calls have happened so far this turn (1 after
    # the first). Incremented by retrieve itself on every entry, including
    # loop-back re-entries within the same turn.
    retrieval_attempt: NotRequired[int]
    # The sufficiency checker's raw verdict from the most recent pass --
    # always freshly set by assess_retrieval_sufficiency immediately
    # before route_after_sufficiency_check reads it, so (unlike the two
    # fields above) it needs no separate per-turn reset.
    retrieval_sufficient: NotRequired[bool]

    # Generation outputs.
    answer: NotRequired[str]
    citations: NotRequired[list[CitationState]]
    grounded: NotRequired[bool]
    # 1-based indices into reranked_chunks the generator actually cited
    # (matches context_builder's [n] numbering). None means "cite every
    # reranked chunk" -- ExtractiveAnswerGenerator's behavior, since it has
    # no way to report which chunks it "used".
    citation_indices: NotRequired[list[int] | None]
