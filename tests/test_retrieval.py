"""
Retrieval quality tests: for each labeled question in sample_questions.json,
the expected category should appear among the top retrieved chunks.

This intentionally does NOT assert anything about exact chunk text or LLM
wording — only that semantic retrieval routes a question to roughly the
right part of the knowledge base. That's the non-brittle thing to check;
exact wording is the LLM's job (generation), not retrieval's.

Embeddings run locally (sentence-transformers, no API key needed — see
backend/app/rag/embeddings.py) so the only prerequisite is a built vector
index. If it's empty, these tests are skipped with a clear reason rather
than failing.

Run with:
    cd backend && source .venv/bin/activate
    pytest ../tests/test_retrieval.py -v
"""
import json
from pathlib import Path

import pytest

from app.rag.embeddings import EmbeddingConfigError, embed_query
from app.rag.vector_store import get_collection, similarity_search

SAMPLE_QUESTIONS_PATH = Path(__file__).resolve().parent / "sample_questions.json"

# Categories actually present in ingestion/sources.json — retrieval can only
# be meaningfully evaluated against these. "refusal" (private-data questions)
# never reach retrieval at all (see test_safety.py) so they're excluded here.
RETRIEVABLE_CATEGORIES = {
    "orientation",
    "welcome_week",
    "housing",
    "move_in",
    "international",
    "icard",
    "transportation",
    "health",
    "accessibility",
    "dining",
    "academics",
    "technology",
    "library",
    "recreation",
    "safety",
    "counseling",
    "parking",
    "financial_aid",
    "student_life",
}

TOP_K = 5


def _load_retrievable_cases() -> list[dict]:
    with SAMPLE_QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        all_cases = json.load(f)
    return [c for c in all_cases if c["expected_category"] in RETRIEVABLE_CATEGORIES]


def _index_is_ready() -> bool:
    try:
        return get_collection().count() > 0
    except Exception:
        return False


RETRIEVABLE_CASES = _load_retrievable_cases()

_SKIP_REASON = (
    "Vector index is empty. Run `cd ingestion && python refresh_index.py` "
    "before running retrieval tests (no API key needed — embeddings run locally)."
)


def test_sample_questions_file_has_expected_coverage():
    """Sanity check on the dataset itself, independent of the index."""
    with SAMPLE_QUESTIONS_PATH.open("r", encoding="utf-8") as f:
        all_cases = json.load(f)
    assert len(all_cases) >= 50
    categories_covered = {c["expected_category"] for c in all_cases}
    assert RETRIEVABLE_CATEGORIES.issubset(categories_covered)
    assert "refusal" in categories_covered


@pytest.mark.skipif(not _index_is_ready(), reason=_SKIP_REASON)
@pytest.mark.parametrize(
    "case",
    RETRIEVABLE_CASES,
    ids=[c["question"] for c in RETRIEVABLE_CASES],
)
def test_expected_category_in_top_results(case):
    question = case["question"]
    expected_category = case["expected_category"]

    try:
        query_embedding = embed_query(question)
    except EmbeddingConfigError as exc:
        pytest.skip(f"Embeddings not available: {exc}")

    results = similarity_search(query_embedding, top_k=TOP_K)
    retrieved_categories = [r["category"] for r in results]

    assert expected_category in retrieved_categories, (
        f"Expected category {expected_category!r} not found in top "
        f"{TOP_K} results for {question!r}: {retrieved_categories}"
    )
