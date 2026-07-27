import re
from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import BaseMessage

from app.graph.state import RetrievedChunkState
from app.models.conversation_session import StudentType

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
# Split on sentence-ending punctuation followed by whitespace -- not a real
# sentence tokenizer (doesn't handle "Dr.", "e.g.", decimals, etc.), but
# ingested chunk content is already-cleaned prose (see html_loader.py), and
# an occasional over-split just means a slightly shorter "sentence" gets
# scored, not a wrong answer.
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_STOPWORDS = frozenset(
    "a an the this that these those is are was were be been being do does did "
    "to of in on for and or how what when where who which i you your my me can "
    "will would should could i'm im whats what's hows how's".split()
)
# How many of the top reranked chunks ExtractiveAnswerGenerator draws from
# (Settings.rerank_top_k caps reranked_chunks at 8, so this never exceeds
# what's already been computed). Raised from 3 to 5 after a real live
# case: "how do I get from O'Hare without a car" had the one genuinely
# on-point chunk (Peoria Charter bus service, naming O'Hare specifically)
# rank 4th post-rerank, behind three chunks that were topically related
# (airport codes, driving directions, a bus-tracker app) but didn't
# actually answer the question -- confirmed live that raising this to 5
# surfaces it. This is a breadth/coherence tradeoff, not a pure quality
# knob: more chunks means more source diversity but a longer, more
# list-like answer, so don't raise it further without a reason.
_MAX_SOURCE_CHUNKS = 5


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_PATTERN.findall(text.lower()) if t not in _STOPWORDS}


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_PATTERN.split(normalized) if s.strip()]


_GREETING_ANSWER = (
    "Hello! I'm IlliniAssist AI, an assistant for UIUC admissions, housing, registration, "
    "financial aid, international student services, and more. What can I help you with?"
)

_NO_RESULTS_ANSWER = (
    "I couldn't find anything in official UIUC sources about that. Could you rephrase your "
    "question, or ask about a specific topic like admissions, housing, or financial aid?"
)


@dataclass(frozen=True)
class GeneratedAnswer:
    text: str
    grounded: bool
    # 1-based indices into the context sections actually cited, matching
    # context_builder's [n] numbering. None means "no citation filtering
    # information available" -- citation_generator falls back to citing
    # every chunk it was given, which in practice only happens via
    # greeting_answer()/no_results_answer() below (both real generators,
    # Groq and Extractive, always set this explicitly), and both of those
    # are only ever reached with an empty chunk list anyway.
    citation_indices: list[int] | None = None


class AnswerGenerator(Protocol):
    """The generate_response node depends on this, not a concrete LLM client,
    so Phase 6 can plug in real Groq generation behind the same interface
    without touching graph structure or any other node. Async because a real
    implementation makes a network call; ExtractiveAnswerGenerator just
    doesn't await anything inside its own async def.
    """

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunkState],
        *,
        context: str,
        history: list[BaseMessage],
        student_type: StudentType | None,
    ) -> GeneratedAnswer: ...


class ExtractiveAnswerGenerator:
    """Dependency-free fallback: deterministic, no LLM call, no API key
    required -- used automatically whenever GROQ_API_KEY is unset (see
    app/api/dependencies.py::get_answer_generator), and by tests that want
    to exercise graph control flow without a real key.

    Doesn't synthesize prose the way an LLM would, but does more than dump
    the top chunk verbatim (the original Phase 5 placeholder behavior,
    still used as the fallback below when nothing scores): for each of the
    top `_MAX_SOURCE_CHUNKS` reranked chunks, picks the single sentence
    with the most query-term overlap. Reranking already found the right
    *chunks*; this is a cheap, local way to find the right *sentence*
    within them, since a whole chunk is often a paragraph of which only
    one sentence actually answers the question (confirmed live: "Where do
    freshmen live on campus?" against a top chunk that was mostly
    "how to choose your housing" navigational text, not an answer).
    """

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunkState],
        *,
        context: str,
        history: list[BaseMessage],
        student_type: StudentType | None,
    ) -> GeneratedAnswer:
        if not chunks:
            return GeneratedAnswer(text=_NO_RESULTS_ANSWER, grounded=False)

        query_terms = _tokenize(query)
        picks: list[tuple[int, str]] = []  # (0-based index into `chunks`, best sentence)
        seen_sentences: set[str] = set()
        for chunk_index, chunk in enumerate(chunks[:_MAX_SOURCE_CHUNKS]):
            sentences = _split_sentences(chunk["content"])
            if not sentences:
                continue
            best_sentence, best_overlap = sentences[0], -1
            for sentence in sentences:
                overlap = len(query_terms & _tokenize(sentence))
                if overlap > best_overlap:
                    best_sentence, best_overlap = sentence, overlap
            # Different pages sometimes share boilerplate ("check the USCIS
            # website...") -- confirmed live, two distinct chunks both
            # scoring the same sentence as their best match. Skip rather
            # than show the identical line twice.
            if best_overlap > 0 and best_sentence not in seen_sentences:
                picks.append((chunk_index, best_sentence))
                seen_sentences.add(best_sentence)

        if not picks:
            # No sentence in any of the top chunks shares a query term --
            # fall back to the original placeholder behavior (the full top
            # chunk) rather than returning something emptier than before.
            top = chunks[0]
            text = f"According to {top['title']} ({top['department']}):\n\n{top['content']}"
            return GeneratedAnswer(text=text, grounded=True, citation_indices=[1])

        if len(picks) == 1:
            chunk_index, sentence = picks[0]
            chunk = chunks[chunk_index]
            text = f"According to {chunk['title']} ({chunk['department']}):\n\n{sentence}"
        else:
            lines = [
                f"- {sentence} ({chunks[chunk_index]['department']})"
                for chunk_index, sentence in picks
            ]
            text = "Based on official UIUC sources:\n\n" + "\n".join(lines)

        citation_indices = sorted({chunk_index + 1 for chunk_index, _ in picks})
        return GeneratedAnswer(text=text, grounded=True, citation_indices=citation_indices)


def greeting_answer() -> GeneratedAnswer:
    return GeneratedAnswer(text=_GREETING_ANSWER, grounded=True)


def no_results_answer() -> GeneratedAnswer:
    return GeneratedAnswer(text=_NO_RESULTS_ANSWER, grounded=False)
