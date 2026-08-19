import pytest

from app.core.config import get_settings
from app.graph.state import RetrievedChunkState
from app.llm.retrieval_agent import LlmRetrievalSufficiencyChecker

pytestmark = pytest.mark.skipif(
    not get_settings().groq_api_key, reason="GROQ_API_KEY not configured"
)


async def test_assess_reports_sufficient_when_context_answers_the_question() -> None:
    checker = LlmRetrievalSufficiencyChecker()
    chunks: list[RetrievedChunkState] = [
        {
            "chunk_id": "11111111-1111-1111-1111-111111111111",
            "document_id": "22222222-2222-2222-2222-222222222222",
            "content": (
                "Freshmen must live in undergraduate residence halls during their first year."
            ),
            "title": "Undergraduate Housing",
            "url": "https://example.illinois.edu/housing",
            "department": "University Housing",
            "topic": "housing",
            "subtopic": None,
            "fused_score": 1.0,
        }
    ]

    result = await checker.assess(
        query="Where do freshmen live on campus?",
        context="[1] Undergraduate Housing (University Housing):\n" + chunks[0]["content"],
        chunks=chunks,
    )

    assert result.sufficient is True
    assert result.reformulated_query is None


async def test_assess_reports_insufficient_with_a_reformulation_when_context_is_off_topic() -> None:
    checker = LlmRetrievalSufficiencyChecker()
    chunks: list[RetrievedChunkState] = [
        {
            "chunk_id": "11111111-1111-1111-1111-111111111111",
            "document_id": "22222222-2222-2222-2222-222222222222",
            "content": "The main library is open twenty-four hours during finals week.",
            "title": "Library Hours",
            "url": "https://example.illinois.edu/library",
            "department": "University Library",
            "topic": "libraries",
            "subtopic": None,
            "fused_score": 1.0,
        }
    ]

    result = await checker.assess(
        query="What is the tuition cost for out-of-state graduate students?",
        context="[1] Library Hours (University Library):\n" + chunks[0]["content"],
        chunks=chunks,
    )

    assert result.sufficient is False
    assert result.reformulated_query
    assert len(result.reformulated_query) > 0
