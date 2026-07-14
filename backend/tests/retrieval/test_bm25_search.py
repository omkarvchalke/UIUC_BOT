import uuid

from app.models.document import DocumentChunk
from app.retrieval.bm25_search import BM25Search


def _chunk(content: str) -> DocumentChunk:
    return DocumentChunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_number=1,
        content=content,
        char_count=len(content),
    )


def test_empty_corpus_returns_no_results() -> None:
    search = BM25Search([])
    assert search.search("housing", limit=5) == []


def test_finds_chunk_containing_query_terms() -> None:
    chunks = [
        _chunk("Freshmen must live in undergraduate residence halls during their first year."),
        _chunk("The library is open twenty-four hours during finals week."),
        _chunk("Meal plans include Classic Meals and Dining Dollars."),
    ]
    search = BM25Search(chunks)

    results = search.search("residence halls freshmen", limit=5)

    assert len(results) >= 1
    assert results[0].chunk.content == chunks[0].content


def test_ranks_more_relevant_chunk_first() -> None:
    chunks = [
        _chunk("The Grainger Engineering Library has extended hours during finals."),
        _chunk("Housing applications for freshmen open in the spring semester."),
        _chunk("Housing housing housing: freshmen housing options and freshmen housing rates."),
    ]
    search = BM25Search(chunks)

    results = search.search("freshmen housing", limit=3)

    assert results[0].chunk.content.count("housing") > results[-1].chunk.content.count("housing")


def test_query_with_no_matching_terms_returns_no_results() -> None:
    chunks = [_chunk("Campus recreation membership includes access to the gym.")]
    search = BM25Search(chunks)

    results = search.search("zzzznonexistenttermzzzz", limit=5)

    assert results == []


def test_results_respect_limit() -> None:
    chunks = [_chunk(f"Parking permit information document number {i}.") for i in range(10)]
    search = BM25Search(chunks)

    results = search.search("parking permit", limit=3)

    assert len(results) <= 3
