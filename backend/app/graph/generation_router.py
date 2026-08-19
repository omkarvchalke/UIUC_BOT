from langchain_core.messages import BaseMessage

from app.graph.generation import (
    ExtractiveAnswerGenerator,
    GeneratedAnswer,
    _split_sentences,
    _tokenize,
)
from app.graph.state import RetrievedChunkState
from app.llm.groq_answer_generator import GroqAnswerGenerator
from app.models.conversation_session import StudentType

# These queries structurally can't be answered by picking one sentence per chunk --
# ExtractiveAnswerGenerator's whole design -- regardless of how well any single chunk scores:
# answering them requires relating or contrasting facts that live in different sentences or
# chunks. "both X and Y" is checked separately (paired with " and ") to avoid matching every
# sentence that happens to contain the word "both".
_COMPARISON_PATTERNS = (
    "difference between",
    "differ from",
    " vs ",
    " vs. ",
    "versus",
    "compare",
    "which is better",
)


def _looks_like_comparison(query: str) -> bool:
    lowered = query.lower()
    if "both " in lowered and " and " in lowered:
        return True
    return any(pattern in lowered for pattern in _COMPARISON_PATTERNS)


def _needs_synthesis(
    query: str, chunks: list[RetrievedChunkState], extractive_result: GeneratedAnswer
) -> bool:
    """True when the retrieved context looks like it needs combining information across
    sentences or chunks that ExtractiveAnswerGenerator's one-sentence-per-chunk picker can't
    produce, even when it picked something.

    Signal 1 (nothing grounded): extractive found nothing that cleared the rerank floor -- give
    Groq a shot at the exact same context; its own honest grounded=false self-report (see
    app/prompts/rag_system_prompt.txt, rule 2) means this can't make things worse.

    Signal 2 (comparison/aggregation phrasing): see _looks_like_comparison.

    Signal 3 (fragmented coverage): among the chunks extractive actually cited, some query terms
    are only ever found by combining multiple sentences -- no single sentence anywhere in those
    chunks covers everything the chunks collectively do. This is the general form of the
    pre-source-fix library-hours bug: a chunk whose real answer is split across lines/sentences
    that each individually share few query terms with the question.
    """
    if not extractive_result.grounded:
        return True
    if _looks_like_comparison(query):
        return True

    query_terms = _tokenize(query)
    if not query_terms:
        return False

    cited_indices = extractive_result.citation_indices or []
    cited_chunks = [chunks[i - 1] for i in cited_indices if 0 < i <= len(chunks)]
    if not cited_chunks:
        return False

    union_terms: set[str] = set()
    best_sentence_overlap = 0
    for chunk in cited_chunks:
        for sentence in _split_sentences(chunk["content"]):
            overlap = query_terms & _tokenize(sentence)
            union_terms |= overlap
            best_sentence_overlap = max(best_sentence_overlap, len(overlap))
    return len(union_terms) > best_sentence_overlap


class RoutingAnswerGenerator:
    """Wraps ExtractiveAnswerGenerator (the default, deterministic, no-LLM-call fast path) and
    GroqAnswerGenerator (real LLM synthesis), picking between them per query rather than at
    deployment time the way settings.groq_generation_enabled's all-or-nothing switch does.
    Escalates to Groq only when _needs_synthesis says the retrieved context looks like it needs
    combining information across sentences or chunks -- the common case never calls Groq at all,
    keeping today's latency/cost/determinism for most queries.

    Groq's own generate() already fails open internally on GroqError (returns an ungrounded
    canned fallback, never raises) -- when that happens, or when Groq's own grounded=false
    self-report fires, this falls back to the already-computed extractive result rather than
    Groq's generic failure text, since extractive's is the more informative message.
    """

    def __init__(self, extractive: ExtractiveAnswerGenerator, groq: GroqAnswerGenerator) -> None:
        self._extractive = extractive
        self._groq = groq

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunkState],
        *,
        context: str,
        history: list[BaseMessage],
        student_type: StudentType | None,
    ) -> GeneratedAnswer:
        extractive_result = await self._extractive.generate(
            query, chunks, context=context, history=history, student_type=student_type
        )

        if not _needs_synthesis(query, chunks, extractive_result):
            return extractive_result

        groq_result = await self._groq.generate(
            query, chunks, context=context, history=history, student_type=student_type
        )

        return groq_result if groq_result.grounded else extractive_result
