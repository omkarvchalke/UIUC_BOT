from dataclasses import dataclass
from typing import Protocol

from app.graph.state import RetrievedChunkState


@dataclass(frozen=True)
class SufficiencyAssessment:
    sufficient: bool
    reformulated_query: str | None
    reasoning: str


class RetrievalSufficiencyChecker(Protocol):
    """Judges whether retrieved_chunks actually contain enough to answer
    the question, and if not, proposes a better search query. The graph's
    assess_retrieval_sufficiency node depends on this, not a concrete LLM
    client -- mirrors the AnswerGenerator Protocol split in generation.py."""

    async def assess(
        self, *, query: str, context: str, chunks: list[RetrievedChunkState]
    ) -> SufficiencyAssessment: ...


class AlwaysSufficientChecker:
    """Dependency-free default: never triggers a retry, no Groq call ever
    made. Used whenever Settings.agentic_retrieval_enabled is False or no
    groq_api_key is configured (see app/api/dependencies.py::
    get_retrieval_sufficiency_checker) -- the retrieve -> re_ranker ->
    context_builder -> assess_retrieval_sufficiency edge is always
    structurally present in the graph, but behaviorally a no-op by
    default, so this feature can never change the default single-pass,
    no-LLM experience."""

    async def assess(
        self, *, query: str, context: str, chunks: list[RetrievedChunkState]
    ) -> SufficiencyAssessment:
        return SufficiencyAssessment(sufficient=True, reformulated_query=None, reasoning="disabled")
