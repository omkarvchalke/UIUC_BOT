"""Retrieval-quality metrics: Precision@k, Recall@k, MRR, Context Precision.

Pure functions -- no network, no DB. Every metric here is computed against
binary ground-truth relevance labels (a set of "correct" URLs), not an
LLM-judged relevance score. This is a legitimate, simpler, well-established
variant of these metrics (RAGAS itself supports both a ground-truth and an
LLM-judged Context Precision), not a "fake" version of them.
"""


def _require_relevant(relevant: set[str]) -> None:
    # An empty `relevant` set means the caller passed a case with no
    # retrieval ground truth at all -- a data-setup bug, since callers
    # should only ever invoke these functions for ground-truth-bearing
    # cases (see EvalCase.expected_relevant_urls). Raising here instead of
    # returning a silent 0.0 keeps that bug from being indistinguishable
    # from "the retriever genuinely found nothing relevant", which is
    # exactly the failure mode this module exists to detect cleanly.
    if not relevant:
        raise ValueError("relevant must be non-empty -- this case has no retrieval ground truth")


def _dedupe_by_document(returned: list[str]) -> list[str]:
    # /api/v1/retrieve ranks individual CHUNKS, so the same document's URL
    # can legitimately appear more than once in `returned` (two different
    # chunks from the same page both ranking in the top k). Precision/
    # Recall/Context Precision are conventionally about distinct relevant
    # DOCUMENTS retrieved, not raw chunk-hit counts -- without this, a
    # single relevant page with two ranked chunks could push recall above
    # 1.0 (confirmed live: exactly this happened for a real query where
    # two "parking permits" chunks both landed in the top 5). Keeps first
    # occurrence, preserving rank order.
    seen: set[str] = set()
    deduped: list[str] = []
    for url in returned:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped


def precision_at_k(returned: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top k distinct-document URLs that are relevant.

    Missing slots (fewer than k distinct documents) count as non-relevant
    -- the standard IR convention, and it correctly penalizes a retriever
    that returns fewer than k distinct results.
    """
    _require_relevant(relevant)
    top_k = _dedupe_by_document(returned)[:k]
    hits = sum(1 for url in top_k if url in relevant)
    return hits / k


def recall_at_k(returned: list[str], relevant: set[str], k: int) -> float:
    """Fraction of all relevant URLs that appear among the top k distinct
    documents returned."""
    _require_relevant(relevant)
    top_k = _dedupe_by_document(returned)[:k]
    hits = sum(1 for url in top_k if url in relevant)
    return hits / len(relevant)


def mean_reciprocal_rank(returned: list[str], relevant: set[str]) -> float:
    """1 / (1-indexed rank of the first relevant URL in `returned`, ranked
    over distinct documents).

    0.0 if no relevant URL appears anywhere in `returned` -- a real
    retrieval-failure signal (the ground truth exists but wasn't found),
    not an error case. Computed over the full deduplicated `returned`
    list, not truncated to any k: a doc that ranked 6th is a materially
    different, more useful signal than "not in the top 5".
    """
    _require_relevant(relevant)
    for rank, url in enumerate(_dedupe_by_document(returned), start=1):
        if url in relevant:
            return 1.0 / rank
    return 0.0


def context_precision(returned: list[str], relevant: set[str]) -> float:
    """RAGAS-style Context Precision, ground-truth (binary relevance) variant.

    For each 1-indexed position i (over distinct documents) where
    returned[i] is relevant, let v_i = 1 (else 0), and
    precision@i = |returned[:i] ∩ relevant| / i. Then:
        context_precision = (sum_i precision@i * v_i) / (sum_i v_i)
    i.e. averaged over the COUNT OF RELEVANT ITEMS ACTUALLY FOUND, not
    len(returned). 0.0 if no relevant item appears at all (sum_i v_i == 0)
    -- same rationale as mean_reciprocal_rank's 0.0 case.
    """
    _require_relevant(relevant)
    hits_so_far = 0
    precision_sum = 0.0
    relevant_found = 0
    for i, url in enumerate(_dedupe_by_document(returned), start=1):
        is_relevant = url in relevant
        if is_relevant:
            hits_so_far += 1
        precision_at_i = hits_so_far / i
        if is_relevant:
            precision_sum += precision_at_i
            relevant_found += 1
    if relevant_found == 0:
        return 0.0
    return precision_sum / relevant_found
