from dataclasses import dataclass
from typing import Protocol

from langchain_core.messages import BaseMessage

from app.graph.state import RetrievedChunkState
from app.models.conversation_session import StudentType

_GREETING_ANSWER = (
    "Hello! I'm IlliniGuide AI, an assistant for UIUC admissions, housing, registration, "
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
    # information available" -- the citation_generator node falls back to
    # citing every chunk it was given, which is what ExtractiveAnswerGenerator
    # (which always uses exactly one chunk anyway) relies on.
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
    """Phase 5 placeholder, kept as a dependency-free fallback: deterministic,
    no LLM call, no API key required.

    Returns the single highest-reranked chunk's content verbatim rather than
    synthesizing prose -- deliberately not trying to sound like a real
    assistant reply. Useful for tests that want to exercise graph control
    flow without a Groq API key, and as what GroqAnswerGenerator degrades to
    is not needed here since the graph handles LLM failures itself (see
    nodes.make_generate_response_node).
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

        top = chunks[0]
        text = f"According to {top['title']} ({top['department']}):\n\n{top['content']}"
        return GeneratedAnswer(text=text, grounded=True)


def greeting_answer() -> GeneratedAnswer:
    return GeneratedAnswer(text=_GREETING_ANSWER, grounded=True)


def no_results_answer() -> GeneratedAnswer:
    return GeneratedAnswer(text=_NO_RESULTS_ANSWER, grounded=False)
