from dataclasses import dataclass
from typing import Protocol

from app.graph.state import RetrievedChunkState

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


class AnswerGenerator(Protocol):
    """The generate_response node depends on this, not a concrete LLM client,
    so Phase 6 (Groq Integration, Prompt Engineering) can swap in a real LLM
    call behind the same interface without touching graph structure or any
    other node."""

    def generate(self, query: str, chunks: list[RetrievedChunkState]) -> GeneratedAnswer: ...


class ExtractiveAnswerGenerator:
    """Phase 5 placeholder: deterministic, no LLM call, no API key required.

    Returns the single highest-reranked chunk's content verbatim rather than
    synthesizing prose -- deliberately not trying to sound like a real
    assistant reply. The point of this phase is proving the graph's control
    flow (routing, retrieval, reranking, citations) is correct and that
    generate_response is cleanly swappable; writing a fluent answer from
    retrieved context is exactly the prompt-engineering problem Phase 6
    owns, and a hand-rolled template here would just be worse work thrown
    away next phase.
    """

    def generate(self, query: str, chunks: list[RetrievedChunkState]) -> GeneratedAnswer:
        if not chunks:
            return GeneratedAnswer(text=_NO_RESULTS_ANSWER, grounded=False)

        top = chunks[0]
        text = f"According to {top['title']} ({top['department']}):\n\n{top['content']}"
        return GeneratedAnswer(text=text, grounded=True)


def greeting_answer() -> GeneratedAnswer:
    return GeneratedAnswer(text=_GREETING_ANSWER, grounded=True)
