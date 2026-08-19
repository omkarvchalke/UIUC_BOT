from app.graph.state import RetrievedChunkState
from app.llm.groq_client import GroqError
from app.llm.retrieval_agent import LlmRetrievalSufficiencyChecker


def test_parse_sufficient_response() -> None:
    raw = '{"sufficient": true, "reformulated_query": null, "reasoning": "context covers it"}'
    result = LlmRetrievalSufficiencyChecker._parse(raw)
    assert result.sufficient is True
    assert result.reformulated_query is None
    assert result.reasoning == "context covers it"


def test_parse_insufficient_response_with_reformulation() -> None:
    raw = (
        '{"sufficient": false, "reformulated_query": "UIUC OPT application steps F-1", '
        '"reasoning": "no steps found"}'
    )
    result = LlmRetrievalSufficiencyChecker._parse(raw)
    assert result.sufficient is False
    assert result.reformulated_query == "UIUC OPT application steps F-1"


def test_parse_missing_reasoning_defaults_safely() -> None:
    raw = '{"sufficient": true, "reformulated_query": null}'
    result = LlmRetrievalSufficiencyChecker._parse(raw)
    assert result.reasoning == ""


def test_parse_empty_reformulated_query_string_normalizes_to_none() -> None:
    raw = '{"sufficient": false, "reformulated_query": "", "reasoning": "x"}'
    result = LlmRetrievalSufficiencyChecker._parse(raw)
    assert result.reformulated_query is None


def test_parse_malformed_json_fails_open_to_sufficient() -> None:
    result = LlmRetrievalSufficiencyChecker._parse("this is not JSON at all.")
    assert result.sufficient is True
    assert result.reasoning == "parse_error"


def test_parse_missing_required_sufficient_key_fails_open() -> None:
    raw = '{"reformulated_query": "x", "reasoning": "y"}'
    result = LlmRetrievalSufficiencyChecker._parse(raw)
    assert result.sufficient is True
    assert result.reasoning == "parse_error"


async def test_assess_returns_sufficient_without_calling_groq_when_no_chunks() -> None:
    class _UncalledClient:
        async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
            raise AssertionError("should not be called when chunks is empty")

    checker = LlmRetrievalSufficiencyChecker(client=_UncalledClient())  # type: ignore[arg-type]
    result = await checker.assess(query="anything", context="", chunks=[])
    assert result.sufficient is True
    assert result.reasoning == "no_chunks"


async def test_assess_fails_open_when_groq_call_raises() -> None:
    # Regression-shaped test, same reasoning as GroqAnswerGenerator's own
    # fail-open-on-GroqError test: this must never break or hang the
    # default experience just because Groq is down/rate-limited.
    class _FailingClient:
        async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
            raise GroqError("boom")

    chunk: RetrievedChunkState = {
        "chunk_id": "1",
        "document_id": "1",
        "content": "Some content.",
        "title": "Title",
        "url": "https://example.illinois.edu",
        "department": "Dept",
        "topic": "libraries",
        "subtopic": None,
        "fused_score": 1.0,
    }

    checker = LlmRetrievalSufficiencyChecker(client=_FailingClient())  # type: ignore[arg-type]
    result = await checker.assess(query="What are the library hours?", context="[1] Some content.", chunks=[chunk])
    assert result.sufficient is True
    assert result.reasoning == "groq_error"


async def test_assess_parses_a_successful_groq_response() -> None:
    class _StubClient:
        async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
            return '{"sufficient": false, "reformulated_query": "better query", "reasoning": "thin"}'

    chunk: RetrievedChunkState = {
        "chunk_id": "1",
        "document_id": "1",
        "content": "Some content.",
        "title": "Title",
        "url": "https://example.illinois.edu",
        "department": "Dept",
        "topic": "libraries",
        "subtopic": None,
        "fused_score": 1.0,
    }

    checker = LlmRetrievalSufficiencyChecker(client=_StubClient())  # type: ignore[arg-type]
    result = await checker.assess(query="q", context="[1] Some content.", chunks=[chunk])
    assert result.sufficient is False
    assert result.reformulated_query == "better query"
