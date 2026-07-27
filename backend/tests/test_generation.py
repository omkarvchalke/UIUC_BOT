from app.graph.generation import ExtractiveAnswerGenerator
from app.graph.state import RetrievedChunkState


def _chunk(*, content: str, title: str = "Title", department: str = "Dept") -> RetrievedChunkState:
    return {
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


async def test_generate_with_no_chunks_returns_no_results() -> None:
    generator = ExtractiveAnswerGenerator()
    result = await generator.generate("anything", [], context="", history=[], student_type=None)
    assert result.grounded is False
    assert "couldn't find" in result.text


async def test_generate_picks_the_relevant_sentence_not_the_whole_chunk() -> None:
    # Regression case for the real live behavior this was built to fix: a
    # chunk that's mostly navigational text with one sentence that actually
    # answers the question.
    generator = ExtractiveAnswerGenerator()
    chunk = _chunk(
        content=(
            "It's important to do your research before choosing a hall. "
            "Freshmen must live in undergraduate residence halls during their first year. "
            "Check out our incoming student page for more resources."
        )
    )

    result = await generator.generate(
        "Where do freshmen live?", [chunk], context="", history=[], student_type=None
    )

    assert result.grounded is True
    assert "Freshmen must live in undergraduate residence halls" in result.text
    assert "incoming student page" not in result.text
    assert result.citation_indices == [1]


async def test_generate_draws_from_multiple_chunks_when_several_are_relevant() -> None:
    generator = ExtractiveAnswerGenerator()
    chunks = [
        _chunk(content="OPT allows F-1 students to work after graduation.", title="OPT"),
        _chunk(content="CPT requires an offer letter before starting work.", title="CPT"),
    ]

    result = await generator.generate(
        "What is the difference between OPT and CPT work authorization?",
        chunks,
        context="",
        history=[],
        student_type=None,
    )

    assert result.grounded is True
    assert "OPT allows F-1 students to work after graduation." in result.text
    assert "CPT requires an offer letter before starting work." in result.text
    assert result.citation_indices == [1, 2]


async def test_generate_deduplicates_identical_sentences_from_different_chunks() -> None:
    # Regression test for a real live observation: two different pages
    # sharing boilerplate text ("check the USCIS website...") both scored
    # that exact sentence as their best match, so the answer showed the
    # identical line twice.
    generator = ExtractiveAnswerGenerator()
    chunks = [
        _chunk(content="Please check the USCIS website for the OPT filing address.", title="A"),
        _chunk(content="Please check the USCIS website for the OPT filing address.", title="B"),
        _chunk(content="Graduate students may apply for OPT before thesis defense.", title="C"),
    ]

    result = await generator.generate(
        "How do I apply for OPT?", chunks, context="", history=[], student_type=None
    )

    assert result.text.count("Please check the USCIS website") == 1


async def test_generate_only_draws_from_the_top_max_source_chunks() -> None:
    generator = ExtractiveAnswerGenerator()
    # 6 chunks, all relevant to "parking" -- only the first 5 (the reranked
    # order) should ever be considered.
    chunks = [_chunk(content=f"Parking permit info, source {i}.") for i in range(6)]

    result = await generator.generate(
        "parking permit", chunks, context="", history=[], student_type=None
    )

    assert result.citation_indices is not None
    assert 6 not in result.citation_indices


async def test_generate_falls_back_to_full_chunk_when_nothing_overlaps_the_query() -> None:
    generator = ExtractiveAnswerGenerator()
    chunk = _chunk(content="Library hours are posted on the library website.")

    result = await generator.generate(
        "asdfghjkl qwerty", [chunk], context="", history=[], student_type=None
    )

    assert result.grounded is True
    assert result.text.endswith(chunk["content"])
    assert result.citation_indices == [1]
