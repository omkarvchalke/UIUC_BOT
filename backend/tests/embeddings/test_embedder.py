import math

from app.embeddings.embedder import EMBEDDING_DIMENSION, Embedder


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    return dot / (_norm(a) * _norm(b))


def test_embed_query_returns_correct_dimension() -> None:
    embedder = Embedder()
    vector = embedder.embed_query("What are the housing options for freshmen?")
    assert len(vector) == EMBEDDING_DIMENSION


def test_embed_documents_returns_one_vector_per_text() -> None:
    embedder = Embedder()
    vectors = embedder.embed_documents(["First passage.", "Second passage.", "Third passage."])
    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIMENSION for v in vectors)


def test_embeddings_are_normalized_to_unit_length() -> None:
    embedder = Embedder()
    vector = embedder.embed_query("UIUC library hours")
    assert math.isclose(_norm(vector), 1.0, abs_tol=1e-4)


def test_semantically_similar_texts_are_closer_than_dissimilar_ones() -> None:
    embedder = Embedder()
    query = embedder.embed_query("Where can freshmen live on campus?")
    housing_passage = embedder.embed_documents(
        ["Undergraduate residence halls are available for first-year students."]
    )[0]
    unrelated_passage = embedder.embed_documents(
        ["The university library is open twenty-four hours during finals week."]
    )[0]

    housing_similarity = _cosine(query, housing_passage)
    unrelated_similarity = _cosine(query, unrelated_passage)

    assert housing_similarity > unrelated_similarity
