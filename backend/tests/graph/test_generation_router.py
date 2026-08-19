from app.graph.generation import ExtractiveAnswerGenerator, GeneratedAnswer
from app.graph.generation_router import (
    RoutingAnswerGenerator,
    _looks_like_comparison,
    _needs_synthesis,
)
from app.graph.state import RetrievedChunkState
from app.llm.groq_answer_generator import GroqAnswerGenerator
from app.llm.groq_client import GroqError


def _chunk(
    *,
    content: str,
    title: str = "Title",
    department: str = "Dept",
    rerank_score: float | None = None,
) -> RetrievedChunkState:
    chunk: RetrievedChunkState = {
        "chunk_id": "1",
        "document_id": "1",
        "content": content,
        "title": title,
        "url": "https://example.illinois.edu",
        "department": department,
        "topic": "housing",
        "subtopic": None,
        "fused_score": 1.0,
    }
    if rerank_score is not None:
        chunk["rerank_score"] = rerank_score
    return chunk


class _UncalledClient:
    async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
        raise AssertionError("Groq should not have been called")


class _StubClient:
    def __init__(self, response: str) -> None:
        self._response = response

    async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
        return self._response


class _FailingClient:
    async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
        raise GroqError("boom")


def _grounded(citation_indices: list[int]) -> GeneratedAnswer:
    return GeneratedAnswer(text="answer", grounded=True, citation_indices=citation_indices)


def _ungrounded() -> GeneratedAnswer:
    return GeneratedAnswer(text="I couldn't find anything.", grounded=False, citation_indices=[])


# --- _looks_like_comparison ---


def test_comparison_phrase_detected() -> None:
    assert _looks_like_comparison("What's the difference between the ARC and CRCE?")
    assert _looks_like_comparison("How does OPT differ from CPT?")
    assert _looks_like_comparison("Illini Union vs the Main Library, which has more study space?")
    assert _looks_like_comparison("Is both the ARC and CRCE open on weekends?")


def test_plain_query_not_flagged_as_comparison() -> None:
    assert not _looks_like_comparison("Where do freshmen live on campus?")
    assert not _looks_like_comparison("What are the library hours?")


# --- _needs_synthesis ---


def test_ungrounded_extractive_always_needs_synthesis() -> None:
    assert _needs_synthesis("anything", [], _ungrounded())


def test_comparison_query_needs_synthesis_even_when_grounded() -> None:
    chunk = _chunk(content="The ARC is open 24 hours a day.")
    result = _grounded([1])
    assert _needs_synthesis("What's the difference between the ARC and CRCE?", [chunk], result)


def test_well_covered_single_sentence_does_not_need_synthesis() -> None:
    chunk = _chunk(
        content="Freshmen must live in undergraduate residence halls during their first year."
    )
    result = _grounded([1])
    assert not _needs_synthesis("Where do freshmen live?", [chunk], result)


def test_fragmented_coverage_across_sentences_needs_synthesis() -> None:
    # Same shape as the pre-fix library-hours bug: the query's terms are split across two
    # sentences in the same chunk, so no single sentence covers what the chunk as a whole does.
    chunk = _chunk(
        content=(
            "Main Library hours for the next seven days:\n"
            "Today: open 08:30 AM - 05:00 PM.\n"
            "Main Library is a large research library."
        )
    )
    result = _grounded([1])
    assert _needs_synthesis("What are the library hours today?", [chunk], result)


def test_empty_query_terms_does_not_need_synthesis() -> None:
    chunk = _chunk(content="Some content.")
    result = _grounded([1])
    assert not _needs_synthesis("the a an", [chunk], result)


# --- RoutingAnswerGenerator ---


async def test_well_answered_query_never_calls_groq() -> None:
    router = RoutingAnswerGenerator(
        extractive=ExtractiveAnswerGenerator(),
        groq=GroqAnswerGenerator(client=_UncalledClient()),  # type: ignore[arg-type]
    )
    chunk = _chunk(
        content="Freshmen must live in undergraduate residence halls during their first year."
    )

    result = await router.generate(
        "Where do freshmen live?", [chunk], context="[1] ...", history=[], student_type=None
    )

    assert result.grounded is True
    assert "Freshmen must live in undergraduate residence halls" in result.text


async def test_ungrounded_extractive_escalates_to_groq() -> None:
    router = RoutingAnswerGenerator(
        extractive=ExtractiveAnswerGenerator(),
        groq=GroqAnswerGenerator(
            client=_StubClient(
                '{"answer": "Synthesized answer [1].", "grounded": true, "citations_used": [1]}'
            )
        ),  # type: ignore[arg-type]
    )
    chunk = _chunk(content="Completely unrelated content about parking permits.", rerank_score=0.0)

    result = await router.generate(
        "What is the CC-I certificate?", [chunk], context="[1] ...", history=[], student_type=None
    )

    assert result.grounded is True
    assert result.text == "Synthesized answer [1]."


async def test_groq_failure_falls_back_to_grounded_extractive_result() -> None:
    router = RoutingAnswerGenerator(
        extractive=ExtractiveAnswerGenerator(),
        groq=GroqAnswerGenerator(client=_FailingClient()),  # type: ignore[arg-type]
    )
    chunk = _chunk(content="The ARC is open 24 hours a day, every day of the week.")

    result = await router.generate(
        "What's the difference between the ARC and CRCE?",
        [chunk],
        context="[1] ...",
        history=[],
        student_type=None,
    )

    assert result.grounded is True
    assert "ARC is open 24 hours" in result.text


async def test_both_ungrounded_returns_standard_no_results_message() -> None:
    router = RoutingAnswerGenerator(
        extractive=ExtractiveAnswerGenerator(),
        groq=GroqAnswerGenerator(client=_FailingClient()),  # type: ignore[arg-type]
    )

    result = await router.generate(
        "What is the CC-I certificate?", [], context="", history=[], student_type=None
    )

    assert result.grounded is False
    assert "couldn't find" in result.text
