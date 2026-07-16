from app.graph.state import RetrievedChunkState
from app.llm.groq_answer_generator import GroqAnswerGenerator
from app.llm.groq_client import GroqError


def test_parse_valid_json_response() -> None:
    raw = '{"answer": "Freshmen must live on campus [1].", "grounded": true, "citations_used": [1]}'
    result = GroqAnswerGenerator._parse(raw)
    assert result.text == "Freshmen must live on campus [1]."
    assert result.grounded is True
    assert result.citation_indices == [1]


def test_parse_response_with_no_citations() -> None:
    raw = '{"answer": "I could not find that.", "grounded": false, "citations_used": []}'
    result = GroqAnswerGenerator._parse(raw)
    assert result.grounded is False
    assert result.citation_indices == []


def test_parse_missing_optional_fields_defaults_safely() -> None:
    raw = '{"answer": "Some answer."}'
    result = GroqAnswerGenerator._parse(raw)
    assert result.text == "Some answer."
    assert result.grounded is False
    assert result.citation_indices == []


def test_parse_malformed_json_falls_back_to_raw_text_ungrounded() -> None:
    raw = "This is not JSON at all."
    result = GroqAnswerGenerator._parse(raw)
    assert result.text == raw
    assert result.grounded is False
    assert result.citation_indices is None


def test_parse_json_missing_required_answer_key_falls_back() -> None:
    raw = '{"grounded": true, "citations_used": [1]}'
    result = GroqAnswerGenerator._parse(raw)
    assert result.text == raw
    assert result.grounded is False


async def test_generate_with_no_chunks_returns_no_results_without_calling_groq() -> None:
    generator = GroqAnswerGenerator()
    result = await generator.generate("anything", [], context="", history=[], student_type=None)
    assert result.grounded is False


async def test_generate_falls_back_with_no_citations_when_groq_call_fails() -> None:
    # Regression test for a real bug: a failed Groq call (confirmed live --
    # "max completion tokens reached before generating a valid document" on
    # a library-hours question once the crawler added substantial real
    # library content) used to return citation_indices=None, which
    # citation_generator interprets as "cite every chunk given" -- so the
    # generic "I'm having trouble" fallback text was showing up with real
    # looking sources attached, even though no generation actually
    # succeeded.
    class _FailingClient:
        async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
            raise GroqError("boom")

    generator = GroqAnswerGenerator(client=_FailingClient())  # type: ignore[arg-type]
    chunk: RetrievedChunkState = {
        "chunk_id": "1",
        "document_id": "1",
        "content": "Some content.",
        "title": "Title",
        "url": "https://example.illinois.edu",
        "department": "Dept",
        "topic": "libraries",
        "fused_score": 1.0,
    }

    result = await generator.generate(
        "What are the library hours?",
        [chunk],
        context="[1] Some content.",
        history=[],
        student_type=None,
    )

    assert result.grounded is False
    assert result.citation_indices == []
