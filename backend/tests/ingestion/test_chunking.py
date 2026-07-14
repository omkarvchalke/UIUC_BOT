import pytest

from app.ingestion.chunking import ChunkerConfig, RecursiveCharacterChunker


def test_empty_text_produces_no_chunks() -> None:
    chunker = RecursiveCharacterChunker()
    assert chunker.split("") == []
    assert chunker.split("   \n\n  ") == []


def test_short_text_produces_a_single_chunk() -> None:
    chunker = RecursiveCharacterChunker(ChunkerConfig(chunk_size=1000, chunk_overlap=100))
    text = "This is a short paragraph about UIUC housing."
    chunks = chunker.split(text)
    assert chunks == [text]


def test_long_text_is_split_into_multiple_chunks_within_size() -> None:
    config = ChunkerConfig(chunk_size=200, chunk_overlap=40)
    chunker = RecursiveCharacterChunker(config)
    paragraph = "UIUC students can register for classes through the Student Self-Service portal. "
    text = paragraph * 10

    chunks = chunker.split(text)

    assert len(chunks) > 1
    # chunk_size is a soft target (an overlap-carried atom can push slightly
    # over), but chunks should never balloon far past it.
    assert all(len(chunk) <= config.chunk_size + 100 for chunk in chunks)


def test_consecutive_chunks_overlap() -> None:
    config = ChunkerConfig(chunk_size=100, chunk_overlap=30)
    chunker = RecursiveCharacterChunker(config)
    text = " ".join(f"word{i}" for i in range(60))

    chunks = chunker.split(text)

    assert len(chunks) > 1
    for first, second in zip(chunks, chunks[1:], strict=False):
        first_words = first.split()
        second_words = second.split()
        assert set(first_words[-3:]) & set(second_words[:3])


def test_no_word_is_lost_across_chunks() -> None:
    config = ChunkerConfig(chunk_size=150, chunk_overlap=20)
    chunker = RecursiveCharacterChunker(config)
    words = [f"token{i}" for i in range(200)]
    text = " ".join(words)

    chunks = chunker.split(text)
    seen_words: set[str] = set()
    for chunk in chunks:
        seen_words.update(chunk.split())

    assert set(words) <= seen_words


def test_respects_paragraph_boundaries_when_possible() -> None:
    config = ChunkerConfig(chunk_size=60, chunk_overlap=10)
    chunker = RecursiveCharacterChunker(config)
    text = "First paragraph here.\n\nSecond paragraph here.\n\nThird paragraph here."

    chunks = chunker.split(text)

    assert any("First paragraph" in chunk for chunk in chunks)
    assert any("Third paragraph" in chunk for chunk in chunks)


def test_single_huge_word_is_hard_split() -> None:
    config = ChunkerConfig(chunk_size=50, chunk_overlap=10)
    chunker = RecursiveCharacterChunker(config)
    text = "a" * 500

    chunks = chunker.split(text)

    assert len(chunks) > 1
    assert "".join(chunks).count("a") >= 500


def test_overlap_must_be_smaller_than_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RecursiveCharacterChunker(ChunkerConfig(chunk_size=100, chunk_overlap=100))
