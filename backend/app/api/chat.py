import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.safety import classify
from app.models.schemas import ChatRequest, ChatResponse, ChatTurn, ConfidenceLevel, SourceRef
from app.rag.embeddings import EmbeddingConfigError
from app.rag.generator import (
    GenerationConfigError,
    generate_answer,
    generate_answer_stream,
    generate_metadata,
)
from app.rag.retriever import DEFAULT_TOP_K, retrieve

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])

# Heuristic thresholds on retrieval similarity score (see vector_store.similarity_search,
# cosine distance -> 0-1-ish score). These are a starting point, not
# empirically calibrated — real embeddings for genuinely relevant Q&A pairs
# often score lower than intuition suggests, so revisit once there's real
# usage data (see docs/rag-pipeline.md and Phase 13 evaluation).
HIGH_CONFIDENCE_THRESHOLD = 0.45
MEDIUM_CONFIDENCE_THRESHOLD = 0.30

INSUFFICIENT_CONTEXT_ANSWER = (
    "I don't have enough information from public sources to answer this confidently. "
    "Please contact the relevant university office for official guidance."
)
INSUFFICIENT_CONTEXT_NEXT_STEPS = [
    "Contact the relevant university office for official guidance.",
]
BLOCKED_NEXT_STEPS = [
    "Use the official university portal or contact the relevant office directly.",
]


def _compute_confidence(chunks: list[dict]) -> ConfidenceLevel:
    if not chunks:
        return "low"
    top_scores = [c["score"] for c in chunks[:3]]
    avg_score = sum(top_scores) / len(top_scores)
    if avg_score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    if avg_score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    return "low"


def _dedupe_sources(chunks: list[dict]) -> list[SourceRef]:
    seen: set[str] = set()
    sources: list[SourceRef] = []
    for chunk in chunks:
        url = chunk["source_url"]
        if url in seen:
            continue
        seen.add(url)
        sources.append(
            SourceRef(
                title=chunk["source_title"],
                url=url,
                category=chunk["category"],
                department=chunk["department"],
            )
        )
    return sources


def _build_retrieval_query(question: str, history: list[ChatTurn]) -> str:
    """Cheap heuristic for retrieval on follow-up questions: prepend the
    most recent user turn to the current question so a short follow-up
    like "what about grad students?" still retrieves relevant chunks on
    its own, without a separate query-rewriting LLM call."""
    for turn in reversed(history):
        if turn.role == "user":
            return f"{turn.content} {question}"
    return question


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    safety = classify(request.question)

    # Private-data requests are intercepted here, before any embedding or
    # LLM call is made — no exceptions, regardless of index/API state.
    if safety.is_blocked:
        return ChatResponse(
            answer=safety.escalation_note,
            sources=[],
            confidence="low",
            next_steps=BLOCKED_NEXT_STEPS,
            requires_official_confirmation=True,
        )

    retrieval_query = _build_retrieval_query(request.question, request.history)
    try:
        chunks = retrieve(retrieval_query, top_k=DEFAULT_TOP_K)
    except EmbeddingConfigError as exc:
        logger.error("Chat retrieval failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not chunks:
        next_steps = list(INSUFFICIENT_CONTEXT_NEXT_STEPS)
        if safety.escalation_note:
            next_steps.insert(0, safety.escalation_note)
        return ChatResponse(
            answer=INSUFFICIENT_CONTEXT_ANSWER,
            sources=[],
            confidence="low",
            next_steps=next_steps,
            requires_official_confirmation=True,
        )

    confidence = _compute_confidence(chunks)
    sources = _dedupe_sources(chunks)

    history_dicts = [turn.model_dump() for turn in request.history]
    try:
        generated = generate_answer(request.question, chunks, history_dicts)
    except GenerationConfigError as exc:
        logger.error("Chat generation failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    next_steps = generated["next_steps"]

    # The model's self-reported "grounded" flag is a narrow, downward-only
    # signal: it can tell us the retrieved chunks didn't actually answer the
    # question (which retrieval-score-based confidence alone can't catch —
    # e.g. topically-related-but-irrelevant chunks scoring "high"), but it
    # can never raise confidence or claim something it isn't. See
    # generator.py and docs/rag-pipeline.md.
    if not generated["grounded"]:
        confidence = "low"

    requires_confirmation = confidence != "high"

    # Sensitive-but-general topics (immigration/health/financial aid/emergency)
    # still get a real RAG answer, but always lead with an office-escalation
    # next step and always require official confirmation.
    if safety.escalation_note:
        next_steps = [safety.escalation_note] + list(next_steps)
        requires_confirmation = True

    return ChatResponse(
        answer=generated["answer"],
        sources=sources,
        confidence=confidence,
        next_steps=next_steps,
        requires_official_confirmation=requires_confirmation,
    )


@router.post("/chat/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Server-Sent Events version of /chat: streams the answer token-by-token
    as it's generated, then emits one final "done" event with sources,
    confidence, next_steps, and requires_official_confirmation — the same
    fields ChatResponse carries, computed the same way as /chat.

    Event shapes (each a `data: <json>\\n\\n` line):
      {"type": "delta", "text": "..."}                       — repeated
      {"type": "done", "sources": [...], "confidence": ...,
       "next_steps": [...], "requires_official_confirmation": ...}
      {"type": "error", "detail": "..."}                     — terminal

    Errors use an "error" SSE event rather than an HTTP error status,
    because by the time a mid-stream failure happens the 200 response and
    headers have already been sent — there's no way to change the status
    code anymore.
    """
    safety = classify(request.question)

    def event_generator():
        if safety.is_blocked:
            yield _sse({"type": "delta", "text": safety.escalation_note})
            yield _sse(
                {
                    "type": "done",
                    "sources": [],
                    "confidence": "low",
                    "next_steps": BLOCKED_NEXT_STEPS,
                    "requires_official_confirmation": True,
                }
            )
            return

        retrieval_query = _build_retrieval_query(request.question, request.history)
        try:
            chunks = retrieve(retrieval_query, top_k=DEFAULT_TOP_K)
        except EmbeddingConfigError as exc:
            logger.error("Chat stream retrieval failed: %s", exc)
            yield _sse({"type": "error", "detail": str(exc)})
            return

        if not chunks:
            next_steps = list(INSUFFICIENT_CONTEXT_NEXT_STEPS)
            if safety.escalation_note:
                next_steps.insert(0, safety.escalation_note)
            yield _sse({"type": "delta", "text": INSUFFICIENT_CONTEXT_ANSWER})
            yield _sse(
                {
                    "type": "done",
                    "sources": [],
                    "confidence": "low",
                    "next_steps": next_steps,
                    "requires_official_confirmation": True,
                }
            )
            return

        confidence = _compute_confidence(chunks)
        sources = _dedupe_sources(chunks)
        history_dicts = [turn.model_dump() for turn in request.history]

        answer_parts: list[str] = []
        try:
            for delta in generate_answer_stream(request.question, chunks, history_dicts):
                answer_parts.append(delta)
                yield _sse({"type": "delta", "text": delta})
        except GenerationConfigError as exc:
            logger.error("Chat stream generation failed: %s", exc)
            yield _sse({"type": "error", "detail": str(exc)})
            return

        answer = "".join(answer_parts).strip()
        if not answer:
            answer = INSUFFICIENT_CONTEXT_ANSWER
            yield _sse({"type": "delta", "text": answer})
            metadata = {"next_steps": [], "grounded": False}
        else:
            try:
                metadata = generate_metadata(request.question, chunks, answer)
            except GenerationConfigError as exc:
                # The answer already streamed successfully — don't discard
                # it over a failed follow-up call, just fall back.
                logger.warning("Chat stream metadata call failed, defaulting: %s", exc)
                metadata = {"next_steps": [], "grounded": True}

        if not metadata["grounded"]:
            confidence = "low"

        next_steps = metadata["next_steps"]
        requires_confirmation = confidence != "high"
        if safety.escalation_note:
            next_steps = [safety.escalation_note] + list(next_steps)
            requires_confirmation = True

        yield _sse(
            {
                "type": "done",
                "sources": [s.model_dump() for s in sources],
                "confidence": confidence,
                "next_steps": next_steps,
                "requires_official_confirmation": requires_confirmation,
            }
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")
