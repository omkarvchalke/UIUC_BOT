from app.retrieval.reranker import CrossEncoderReranker


def test_empty_candidates_returns_empty_list() -> None:
    reranker = CrossEncoderReranker()
    assert reranker.rerank("housing", [], top_k=5) == []


def test_more_relevant_passage_is_ranked_first() -> None:
    reranker = CrossEncoderReranker()
    candidates = [
        ("The university library is open twenty-four hours during finals week.", "library"),
        ("Freshmen must live in undergraduate residence halls during their first year.", "housing"),
    ]

    results = reranker.rerank("Where do freshmen live on campus?", candidates, top_k=2)

    assert results[0][0] == "housing"


def test_respects_top_k() -> None:
    reranker = CrossEncoderReranker()
    candidates = [(f"Parking permit document number {i}.", i) for i in range(10)]

    results = reranker.rerank("parking permit", candidates, top_k=3)

    assert len(results) == 3


def test_returns_payload_and_float_score() -> None:
    reranker = CrossEncoderReranker()
    candidates = [("Meal plans include Classic Meals and Dining Dollars.", {"id": 1})]

    results = reranker.rerank("meal plans", candidates, top_k=1)

    payload, score = results[0]
    assert payload == {"id": 1}
    assert isinstance(score, float)
