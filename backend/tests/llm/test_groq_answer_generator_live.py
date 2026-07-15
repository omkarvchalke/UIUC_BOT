import pytest

from app.core.config import get_settings
from app.graph.state import RetrievedChunkState
from app.llm.groq_answer_generator import GroqAnswerGenerator

pytestmark = pytest.mark.skipif(
    not get_settings().groq_api_key, reason="GROQ_API_KEY not configured"
)


async def test_generate_produces_grounded_answer_with_citation() -> None:
    generator = GroqAnswerGenerator()
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
            "fused_score": 1.0,
        }
    ]

    result = await generator.generate(
        "Where do freshmen live on campus?",
        chunks,
        context="[1] Undergraduate Housing (University Housing):\n" + chunks[0]["content"],
        history=[],
        student_type=None,
    )

    assert result.grounded is True
    assert result.citation_indices == [1]
    assert len(result.text) > 0


async def test_generate_reports_ungrounded_when_context_does_not_answer_question() -> None:
    generator = GroqAnswerGenerator()
    chunks: list[RetrievedChunkState] = [
        {
            "chunk_id": "11111111-1111-1111-1111-111111111111",
            "document_id": "22222222-2222-2222-2222-222222222222",
            "content": "The main library is open twenty-four hours during finals week.",
            "title": "Library Hours",
            "url": "https://example.illinois.edu/library",
            "department": "University Library",
            "topic": "libraries",
            "fused_score": 1.0,
        }
    ]

    result = await generator.generate(
        "What is the tuition cost for out-of-state graduate students?",
        chunks,
        context="[1] Library Hours (University Library):\n" + chunks[0]["content"],
        history=[],
        student_type=None,
    )

    assert result.grounded is False
