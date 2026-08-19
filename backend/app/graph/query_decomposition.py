from typing import Protocol


class QueryDecomposer(Protocol):
    """Splits a question into one or more focused sub-questions to search
    independently. The graph's decompose_query node depends on this, not a
    concrete LLM client -- mirrors RetrievalSufficiencyChecker's Protocol
    split (app/graph/retrieval_agent.py)."""

    async def decompose(self, query: str) -> list[str]: ...


class NoOpQueryDecomposer:
    """Dependency-free default: always returns the query unchanged as a
    single-item list, no Groq call ever made. Used whenever
    Settings.query_decomposition_enabled is False or no groq_api_key is
    configured (see app/api/dependencies.py::get_query_decomposer) --
    retrieve's query list (see _retrieval_queries in nodes.py) only ever
    contains one entry by default, so this feature can never change the
    default single-query retrieval experience."""

    async def decompose(self, query: str) -> list[str]:
        return [query]
