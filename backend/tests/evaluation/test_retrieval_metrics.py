from collections.abc import Callable

import pytest

from app.evaluation.retrieval_metrics import (
    context_precision,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)

_URLS = [f"https://example.edu/{letter}" for letter in "abcdef"]
_A, _B, _C, _D, _E, _F = _URLS


def test_precision_and_recall_at_k_hand_computed() -> None:
    # returned = [A, B, C, D, E, F], relevant = {C, F}.
    # top-5 = [A, B, C, D, E] -> 1 hit (C) -> precision@5 = 1/5 = 0.2
    returned = _URLS
    relevant = {_C, _F}

    assert precision_at_k(returned, relevant, 5) == pytest.approx(0.2)
    # recall@5 = hits-in-top-5 (1) / total relevant (2) = 0.5
    assert recall_at_k(returned, relevant, 5) == pytest.approx(0.5)


def test_mean_reciprocal_rank_hand_computed() -> None:
    # First relevant URL (C) is at 1-indexed rank 3 -> MRR = 1/3.
    returned = _URLS
    relevant = {_C, _F}
    assert mean_reciprocal_rank(returned, relevant) == pytest.approx(1 / 3)


def test_context_precision_hand_computed() -> None:
    # positions: 1=A(no) 2=B(no) 3=C(yes, precision@3=1/3) 4=D(no) 5=E(no)
    # 6=F(yes, precision@6=2/6=1/3). Sum of precision-at-hit = 1/3 + 1/3,
    # divided by relevant items found (2) = 1/3.
    returned = _URLS
    relevant = {_C, _F}
    assert context_precision(returned, relevant) == pytest.approx(1 / 3)


def test_relevant_item_never_returned_scores_zero_not_error() -> None:
    returned = [_A, _B, _D]
    relevant = {_C}  # never appears in returned

    assert mean_reciprocal_rank(returned, relevant) == 0.0
    assert context_precision(returned, relevant) == 0.0
    assert precision_at_k(returned, relevant, 3) == 0.0
    assert recall_at_k(returned, relevant, 3) == 0.0


def test_missing_slots_count_as_non_relevant() -> None:
    # Only 2 URLs returned but k=5 -- the missing 3 slots count against
    # precision (standard IR convention), not silently ignored.
    returned = [_A, _C]
    relevant = {_C}
    assert precision_at_k(returned, relevant, 5) == pytest.approx(1 / 5)
    assert recall_at_k(returned, relevant, 5) == pytest.approx(1.0)


@pytest.mark.parametrize("func", [mean_reciprocal_rank, context_precision])
def test_empty_relevant_set_raises_for_rank_metrics(
    func: Callable[[list[str], set[str]], float],
) -> None:
    with pytest.raises(ValueError, match="no retrieval ground truth"):
        func(_URLS, set())


def test_empty_relevant_set_raises_for_precision_and_recall() -> None:
    with pytest.raises(ValueError, match="no retrieval ground truth"):
        precision_at_k(_URLS, set(), 5)
    with pytest.raises(ValueError, match="no retrieval ground truth"):
        recall_at_k(_URLS, set(), 5)


def test_duplicate_urls_are_deduplicated_by_document() -> None:
    # /api/v1/retrieve ranks chunks, not documents -- the same relevant
    # page can appear twice via two different chunks. Regression test for
    # a real bug found via live verification: without deduping, this
    # returned recall@5 = 2.0 (impossible -- recall must be <= 1.0).
    returned = [_A, _C, _C, _D, _C]
    relevant = {_C}

    assert recall_at_k(returned, relevant, 5) == pytest.approx(1.0)
    assert recall_at_k(returned, relevant, 5) <= 1.0
    # Deduplicated top-5 is [A, C, D] (only 3 distinct documents) ->
    # precision@5 = 1 hit / 5 = 0.2, not 3/5.
    assert precision_at_k(returned, relevant, 5) == pytest.approx(1 / 5)
    # C is the 2nd distinct document -> MRR = 1/2, not 1/2 counted 3 times.
    assert mean_reciprocal_rank(returned, relevant) == pytest.approx(0.5)
    assert context_precision(returned, relevant) == pytest.approx(0.5)
