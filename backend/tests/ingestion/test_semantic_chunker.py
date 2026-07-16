from app.ingestion.chunking import ChunkerConfig, RecursiveCharacterChunker
from app.ingestion.extracted_document import ExtractedDocument, Section
from app.ingestion.semantic_chunker import SemanticChunker


def _extracted(
    sections: tuple[Section, ...] | None, *, text: str = "fallback text"
) -> ExtractedDocument:
    return ExtractedDocument(title="T", text=text, last_updated=None, sections=sections)


def test_no_sections_falls_back_to_flat_chunking_with_no_subtopic() -> None:
    config = ChunkerConfig(chunk_size=200, chunk_overlap=40)
    text = "UIUC students can register for classes through the Student Self-Service portal. " * 10
    extracted = _extracted(sections=None, text=text)

    chunker = SemanticChunker(config, min_section_chars=50)
    result = chunker.split(extracted)

    expected_texts = RecursiveCharacterChunker(config).split(text)
    assert [c.text for c in result] == expected_texts
    assert all(c.subtopic is None for c in result)


def test_empty_sections_tuple_falls_back_to_flat_chunking() -> None:
    extracted = _extracted(sections=(), text="Some fallback text.")
    chunker = SemanticChunker(min_section_chars=50)
    result = chunker.split(extracted)
    assert result == [chunker.split(_extracted(sections=None, text="Some fallback text."))[0]]


def test_multi_section_document_tags_each_chunk_with_correct_subtopic() -> None:
    sections = (
        Section(heading_path=("Registration", "Holds"), text="Holds content, well over the floor."),
        Section(
            heading_path=("Registration", "Add/Drop"),
            text="Add/drop content, also well over the floor.",
        ),
    )
    extracted = _extracted(sections=sections)
    chunker = SemanticChunker(
        ChunkerConfig(chunk_size=1000, chunk_overlap=100), min_section_chars=5
    )

    result = chunker.split(extracted)

    assert [c.subtopic for c in result] == ["Registration > Holds", "Registration > Add/Drop"]
    assert result[0].text == sections[0].text
    assert result[1].text == sections[1].text


def test_oversized_section_splits_into_multiple_chunks_sharing_one_subtopic() -> None:
    long_text = "Holds content sentence. " * 60
    sections = (Section(heading_path=("Registration", "Holds"), text=long_text),)
    extracted = _extracted(sections=sections)
    config = ChunkerConfig(chunk_size=300, chunk_overlap=50)

    chunker = SemanticChunker(config, min_section_chars=5)
    result = chunker.split(extracted)

    assert len(result) > 1
    assert all(c.subtopic == "Registration > Holds" for c in result)
    assert all(len(c.text) <= config.chunk_size + 100 for c in result)


def test_small_leading_section_merges_forward_with_next_sections_subtopic() -> None:
    sections = (
        Section(heading_path=(), text="Short intro."),
        Section(heading_path=("Registration",), text="Overview text, still short."),
        Section(
            heading_path=("Registration", "Holds"),
            text="Substantial holds content that clears the minimum section size easily.",
        ),
    )
    extracted = _extracted(sections=sections)
    chunker = SemanticChunker(
        ChunkerConfig(chunk_size=1000, chunk_overlap=100), min_section_chars=60
    )

    result = chunker.split(extracted)

    # "Short intro." (12 chars) and "Overview text, still short." (28 chars)
    # are both under the 60-char floor and not the last section, so both
    # merge forward into the Holds section, taking its subtopic.
    assert len(result) == 1
    assert result[0].subtopic == "Registration > Holds"
    assert "Short intro." in result[0].text
    assert "Overview text, still short." in result[0].text


def test_small_trailing_section_merges_backward_keeping_previous_subtopic() -> None:
    sections = (
        Section(
            heading_path=("Registration", "Holds"),
            text="Substantial holds content that clears the minimum section size easily.",
        ),
        Section(heading_path=("Registration", "Add/Drop"), text="Tiny."),
    )
    extracted = _extracted(sections=sections)
    chunker = SemanticChunker(
        ChunkerConfig(chunk_size=1000, chunk_overlap=100), min_section_chars=60
    )

    result = chunker.split(extracted)

    assert len(result) == 1
    assert result[0].subtopic == "Registration > Holds"
    assert result[0].text.endswith("Tiny.")


def test_subtopic_over_255_chars_trims_outermost_headings_first() -> None:
    long_heading = "X" * 250  # full joined path (250 + " > " + 15) exceeds 255
    sections = (Section(heading_path=(long_heading, "Financial Holds"), text="Some content here."),)
    extracted = _extracted(sections=sections)
    chunker = SemanticChunker(min_section_chars=5)

    result = chunker.split(extracted)

    assert result[0].subtopic == "Financial Holds"
    assert len(result[0].subtopic) <= 255


def test_pathological_single_heading_over_255_chars_hard_truncates() -> None:
    long_heading = "Y" * 300
    sections = (Section(heading_path=(long_heading,), text="Some content here."),)
    extracted = _extracted(sections=sections)
    chunker = SemanticChunker(min_section_chars=5)

    result = chunker.split(extracted)

    assert len(result[0].subtopic) == 255
    assert result[0].subtopic.endswith("...")
