import asyncio
from dataclasses import dataclass

import httpx

from app.evaluation.golden_set import GOLDEN_SET, EvalCase
from app.evaluation.retrieval_metrics import (
    context_precision,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)

# Matches Settings.retrieval_candidate_limit's own default -- the full
# breadth the app's hybrid retrieval stage ever considers, not an
# arbitrary number.
_RETRIEVE_LIMIT = 20
_PRECISION_RECALL_K = 5


@dataclass
class RetrievalEvalResult:
    case: EvalCase
    returned_urls: list[str]
    precision_at_5: float
    recall_at_5: float
    mrr: float
    context_precision: float


async def run_retrieval_case(client: httpx.AsyncClient, case: EvalCase) -> RetrievalEvalResult:
    relevant = set(case.expected_relevant_urls)
    params: dict[str, str | int] = {"query": case.message, "limit": _RETRIEVE_LIMIT}
    # student_type is a hard filter in production retrieval (a document
    # scoped to one student type never surfaces for a different one) --
    # omitting it here would measure something /chat never actually does.
    # topic/audience/document_type are deliberately not passed: those are
    # set by graph nodes this harness isn't exercising, not the retriever
    # itself.
    if case.student_type is not None:
        params["student_type"] = case.student_type.value

    response = await client.get("/api/v1/retrieve", params=params)
    response.raise_for_status()
    body = response.json()
    returned_urls = [result["url"] for result in body["results"]]

    return RetrievalEvalResult(
        case=case,
        returned_urls=returned_urls,
        precision_at_5=precision_at_k(returned_urls, relevant, _PRECISION_RECALL_K),
        recall_at_5=recall_at_k(returned_urls, relevant, _PRECISION_RECALL_K),
        mrr=mean_reciprocal_rank(returned_urls, relevant),
        context_precision=context_precision(returned_urls, relevant),
    )


async def run_retrieval_all(
    base_url: str, *, cases: tuple[EvalCase, ...] = GOLDEN_SET, delay_seconds: float = 0.5
) -> list[RetrievalEvalResult]:
    ground_truth_cases = [case for case in cases if case.expected_relevant_urls]
    results: list[RetrievalEvalResult] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        for case in ground_truth_cases:
            results.append(await run_retrieval_case(client, case))
            await asyncio.sleep(delay_seconds)
    return results
