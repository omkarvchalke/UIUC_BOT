import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.evaluation.golden_set import GOLDEN_SET, EvalCase


@dataclass
class EvalResult:
    case: EvalCase
    passed: bool
    failures: list[str]
    answer: str
    grounded: bool
    needs_clarification: bool
    citation_count: int
    citation_urls: list[str]
    latency_ms: float


async def _create_session(client: httpx.AsyncClient, case: EvalCase) -> str:
    payload: dict[str, str] = {}
    if case.student_type is not None:
        payload["student_type"] = case.student_type.value
    response = await client.post("/api/v1/sessions", json=payload)
    response.raise_for_status()
    return str(response.json()["id"])


def _check(case: EvalCase, body: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    grounded = body["grounded"]
    needs_clarification = body["needs_clarification"]
    citations = body["citations"]

    if case.expect_grounded is not None and grounded != case.expect_grounded:
        failures.append(f"expected grounded={case.expect_grounded}, got {grounded}")
    if case.expect_clarification is not None and needs_clarification != case.expect_clarification:
        failures.append(
            f"expected needs_clarification={case.expect_clarification}, got {needs_clarification}"
        )
    if len(citations) < case.min_citations:
        failures.append(f"expected >= {case.min_citations} citations, got {len(citations)}")

    lowered = body["answer"].lower()
    for phrase in case.forbidden_phrases:
        if phrase in lowered:
            failures.append(f"answer contains forbidden hedge phrase: {phrase!r}")

    return failures


async def run_case(client: httpx.AsyncClient, case: EvalCase) -> EvalResult:
    session_id = await _create_session(client, case)
    start = time.perf_counter()
    response = await client.post(
        "/api/v1/chat", json={"session_id": session_id, "message": case.message}
    )
    latency_ms = (time.perf_counter() - start) * 1000
    response.raise_for_status()
    body = response.json()

    failures = _check(case, body)
    return EvalResult(
        case=case,
        passed=not failures,
        failures=failures,
        answer=body["answer"],
        grounded=body["grounded"],
        needs_clarification=body["needs_clarification"],
        citation_count=len(body["citations"]),
        citation_urls=[citation["url"] for citation in body["citations"]],
        latency_ms=latency_ms,
    )


async def run_all(
    base_url: str, *, cases: tuple[EvalCase, ...] = GOLDEN_SET, delay_seconds: float = 1.0
) -> list[EvalResult]:
    # Sessions themselves aren't rate-limited, but /chat is (see
    # app/core/rate_limit.py) -- a delay between cases keeps a full golden
    # set run comfortably under that limit regardless of how fast Groq
    # happens to respond.
    results: list[EvalResult] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        for case in cases:
            results.append(await run_case(client, case))
            await asyncio.sleep(delay_seconds)
    return results
