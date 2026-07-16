import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.core.exceptions import SessionNotFoundError
from app.core.logging import get_logger
from app.graph.dependencies import GraphDependencies
from app.graph.generation import greeting_answer
from app.graph.state import CitationState, GraphState, RetrievedChunkState
from app.retrieval.hybrid_search import RetrievedChunk

logger = get_logger(__name__)

Node = Callable[[GraphState], Awaitable[dict[str, Any]]]

_GREETING_PHRASES = frozenset(
    {"hi", "hello", "hey", "yo", "hiya", "good morning", "good afternoon", "good evening", "howdy"}
)


def _latest_human_message(state: GraphState) -> str:
    for message in reversed(state["messages"]):
        if isinstance(message, HumanMessage):
            content = message.content
            return content if isinstance(content, str) else str(content)
    return ""


def _to_chunk_state(
    chunk: RetrievedChunk, *, rerank_score: float | None = None
) -> RetrievedChunkState:
    state: RetrievedChunkState = {
        "chunk_id": str(chunk.chunk_id),
        "document_id": str(chunk.document_id),
        "content": chunk.content,
        "title": chunk.title,
        "url": chunk.url,
        "department": chunk.department,
        "topic": chunk.topic.value,
        "fused_score": chunk.fused_score,
    }
    if rerank_score is not None:
        state["rerank_score"] = rerank_score
    return state


def make_load_session_node(deps: GraphDependencies) -> Node:
    async def load_session(state: GraphState) -> dict[str, Any]:
        try:
            session = await deps.session_service.get_session(uuid.UUID(state["session_id"]))
        except SessionNotFoundError:
            logger.warning("graph_session_not_found", session_id=state["session_id"])
            return {}

        return {
            "student_type": session.student_type,
            "semester": session.semester,
            "college": session.college,
            "department": session.department,
        }

    return load_session


def make_check_student_profile_node() -> Node:
    async def check_student_profile(state: GraphState) -> dict[str, Any]:
        # Persisted checkpointer state means len(messages) > 1 on any turn
        # after the first for this session -- only offer to ask about
        # student type once, on a session's very first message, rather than
        # interrupting every turn where it happens to still be unset.
        is_first_turn = len(state["messages"]) <= 1
        missing_profile = (
            state.get("student_type") is None
            and not state.get("profile_asked", False)
            and is_first_turn
        )
        return {
            "needs_clarification": missing_profile,
            "clarification_reason": "missing_profile" if missing_profile else None,
        }

    return check_student_profile


def make_intent_detection_node() -> Node:
    async def intent_detection(state: GraphState) -> dict[str, Any]:
        message = _latest_human_message(state).strip().lower()
        # Rule-based greeting detection only. Reliably detecting "is this
        # in-scope for UIUC at all" needs real language understanding, which
        # is exactly what Phase 6's LLM call is for -- a keyword heuristic
        # here would misfire constantly and isn't worth building just to
        # have *something* in this slot.
        is_greeting = message in _GREETING_PHRASES or (
            len(message.split()) <= 3 and any(message.startswith(p) for p in _GREETING_PHRASES)
        )
        return {"intent": "greeting" if is_greeting else "question"}

    return intent_detection


def make_question_classification_node(deps: GraphDependencies) -> Node:
    async def question_classification(state: GraphState) -> dict[str, Any]:
        message = _latest_human_message(state)
        result = deps.topic_classifier.classify(message)

        needs_clarification = result.topic is None
        return {
            "topic": result.topic,
            "classification_confidence": result.confidence,
            "needs_clarification": needs_clarification,
            "clarification_reason": "ambiguous_topic" if needs_clarification else None,
        }

    return question_classification


def make_clarification_node() -> Node:
    async def clarification(state: GraphState) -> dict[str, Any]:
        reason = state.get("clarification_reason")
        asking_about_profile = reason == "missing_profile"
        if asking_about_profile:
            text = (
                "Before I answer, it helps to know: are you a freshman, transfer, graduate, "
                "or international student?"
            )
        else:
            text = (
                "I want to make sure I point you to the right official source -- could you say "
                "a bit more about what you're asking? For example, is this about admissions, "
                "housing, financial aid, or something else?"
            )
        update: dict[str, Any] = {
            "answer": text,
            "citations": [],
            "grounded": True,
            "messages": [AIMessage(content=text)],
        }
        if asking_about_profile:
            # Only set on the True path: state updates overwrite the
            # checkpointed value with no reducer, so explicitly writing
            # False here on an ambiguous-topic clarification would erase a
            # True set on an earlier turn instead of leaving it untouched.
            update["profile_asked"] = True
        return update

    return clarification


def make_metadata_filter_node() -> Node:
    async def metadata_filter(state: GraphState) -> dict[str, Any]:
        # A named stage per the spec's graph, even though today it's a
        # pass-through: student_type and topic both already sit in state
        # exactly as the retrieve node needs them. Kept as its own node so
        # any future filter rule has an obvious home separate from the
        # retrieval call itself.
        return {}

    return metadata_filter


# Below this many topic-filtered results, treat the classifier's topic guess
# as more likely wrong than the corpus actually being that thin, and retry
# unfiltered rather than surface a false "nothing found." Chosen to be
# clearly below the reranker's input size (8, see rerank node) -- a
# genuinely on-topic query should comfortably clear this from a corpus with
# real per-topic coverage (see test_sources.py's per-topic coverage check).
_MIN_TOPIC_FILTERED_RESULTS = 3


def make_retrieve_node(deps: GraphDependencies) -> Node:
    async def retrieve(state: GraphState) -> dict[str, Any]:
        query = _latest_human_message(state)
        topic = state.get("topic")
        student_type = state.get("student_type")

        results: list[RetrievedChunk] = []
        topic_filter_applied = False
        if topic is not None:
            results = await deps.hybrid_retriever.search(
                query, limit=20, topic=topic, student_type=student_type
            )
            topic_filter_applied = True

        # Fallback case, and the reason topic isn't just always used as a
        # hard filter: "How do I apply for OPT?" classifies as "admissions"
        # (0.65 confidence, above the clarification threshold) purely from
        # "apply"/"application" word overlap with the admissions topic
        # description, and filtering retrieval to topic=admissions returns
        # nothing -- while the same query with no topic filter ranks the
        # real OPT page #1-2. A well-separated topic (e.g. ISSS/CPT) still
        # gets the precision win of a narrowed candidate set; a
        # misclassified one degrades to today's unfiltered behavior instead
        # of a dead end. student_type stays an unconditional hard filter
        # because it comes from the verified session profile, not a
        # classifier guess.
        if len(results) < _MIN_TOPIC_FILTERED_RESULTS:
            fallback_results = await deps.hybrid_retriever.search(
                query, limit=20, student_type=student_type
            )
            if len(fallback_results) > len(results):
                results = fallback_results
                topic_filter_applied = False

        logger.info(
            "graph_retrieve",
            session_id=state["session_id"],
            topic=topic.value if topic else None,
            topic_filter_applied=topic_filter_applied,
            result_count=len(results),
        )
        return {"retrieved_chunks": [_to_chunk_state(chunk) for chunk in results]}

    return retrieve


def make_reranker_node(deps: GraphDependencies) -> Node:
    async def rerank(state: GraphState) -> dict[str, Any]:
        query = _latest_human_message(state)
        candidates = [(c["content"], c) for c in state.get("retrieved_chunks", [])]
        # Raised from 5: answers were coming back thin partly because the
        # model only had 5 chunks of material to work with even after the
        # prompt was told to be thorough -- 8 gives it enough breadth to
        # cover multi-part questions (e.g. "what do I need to submit")
        # without the context growing unreasonably large (Llama 3.3's
        # context window has plenty of headroom for 8 short-to-medium
        # chunks).
        reranked = deps.reranker.rerank(query, candidates, top_k=8)
        return {"reranked_chunks": [{**chunk, "rerank_score": score} for chunk, score in reranked]}

    return rerank


def make_context_builder_node() -> Node:
    async def context_builder(state: GraphState) -> dict[str, Any]:
        chunks = state.get("reranked_chunks", [])
        context = "\n\n".join(
            f"[{i}] {chunk['title']} ({chunk['department']}):\n{chunk['content']}"
            for i, chunk in enumerate(chunks, start=1)
        )
        return {"context": context}

    return context_builder


def make_generate_response_node(deps: GraphDependencies) -> Node:
    async def generate_response(state: GraphState) -> dict[str, Any]:
        if state.get("intent") == "greeting":
            result = greeting_answer()
        else:
            query = _latest_human_message(state)
            # messages[:-1]: exclude the current turn's just-appended human
            # message from "history" -- it's already passed as `query`.
            result = await deps.answer_generator.generate(
                query,
                state.get("reranked_chunks", []),
                context=state.get("context", ""),
                history=state["messages"][:-1],
                student_type=state.get("student_type"),
            )

        return {
            "answer": result.text,
            "grounded": result.grounded,
            "citation_indices": result.citation_indices,
            "messages": [AIMessage(content=result.text)],
        }

    return generate_response


def make_citation_generator_node() -> Node:
    async def citation_generator(state: GraphState) -> dict[str, Any]:
        if state.get("intent") == "greeting":
            return {"citations": []}

        chunks = state.get("reranked_chunks", [])
        indices = state.get("citation_indices")
        if indices is not None:
            # 1-based indices matching context_builder's [n] numbering.
            chunks = [chunks[i - 1] for i in indices if 0 < i <= len(chunks)]

        seen_urls: set[str] = set()
        citations: list[CitationState] = []
        for chunk in chunks:
            if chunk["url"] in seen_urls:
                continue
            seen_urls.add(chunk["url"])
            citations.append(
                {
                    "title": chunk["title"],
                    "url": chunk["url"],
                    "department": chunk["department"],
                    "topic": chunk["topic"],
                }
            )
        return {"citations": citations}

    return citation_generator


def make_save_conversation_state_node() -> Node:
    # Message history and per-turn routing state are already durable via the
    # graph's Postgres checkpointer (see graph.py) -- nothing to write here
    # for that. This node's job is the structured observability the spec
    # calls for (retrieved-document counts, groundedness, errors) at the
    # point a turn actually completes. Persisting a *learned* student_type
    # back to ConversationSession (SessionService.update_student_type
    # already exists for this) is deferred to Phase 6: parsing "yes I'm a
    # transfer student" out of free text reliably needs the LLM call this
    # phase doesn't have yet, so there's no new profile data to persist here
    # for now.
    async def save_conversation_state(state: GraphState) -> dict[str, Any]:
        topic = state.get("topic")
        logger.info(
            "graph_turn_complete",
            session_id=state["session_id"],
            intent=state.get("intent"),
            topic=topic.value if topic else None,
            needs_clarification=state.get("needs_clarification", False),
            grounded=state.get("grounded"),
            citation_count=len(state.get("citations", [])),
        )
        return {}

    return save_conversation_state
