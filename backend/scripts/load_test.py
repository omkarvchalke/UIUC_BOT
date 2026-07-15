"""Formal latency/load testing against a live, running backend.

Two kinds of measurement:
1. Sequential latency profile per endpoint (mean/p50/p95/p99/max) under
   realistic, non-bursty traffic -- what a single real user experiences.
   Paced to stay under each endpoint's rate limit (app/core/rate_limit.py)
   so these numbers reflect real processing time, not 429s.
2. Concurrent burst behavior against the rate limiter -- fires many
   requests at once to confirm it actually throttles under real
   concurrency, not just the sequential calls
   tests/test_chat_api.py::test_chat_enforces_rate_limit already covers.

Not part of pytest/CI: needs a live backend, a real ingested corpus, and
(for /chat) a working GROQ_API_KEY -- costs real tokens and real wall-clock
time (a full run takes a couple of minutes).

Usage (from backend/):
    uv run python -m scripts.load_test
    uv run python -m scripts.load_test --chat-samples 10 --skip-chat
"""

import argparse
import asyncio
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

QUESTIONS = [
    "What meal plans are available?",
    "How do I apply as a freshman?",
    "What are the transfer admission deadlines?",
    "How do I register for classes?",
    "How do I get a parking permit?",
]


@dataclass
class Timing:
    label: str
    latencies_ms: list[float] = field(default_factory=list)
    statuses: dict[int, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def record(self, elapsed_ms: float, status: int) -> None:
        self.latencies_ms.append(elapsed_ms)
        self.statuses[status] = self.statuses.get(status, 0) + 1

    def report(self) -> str:
        if not self.latencies_ms:
            return f"{self.label}: no samples"
        sorted_ms = sorted(self.latencies_ms)

        def pct(p: float) -> float:
            idx = min(len(sorted_ms) - 1, int(len(sorted_ms) * p))
            return sorted_ms[idx]

        lines = [
            f"{self.label} (n={len(sorted_ms)})",
            f"  mean={statistics.mean(sorted_ms):.0f}ms  p50={pct(0.5):.0f}ms  "
            f"p95={pct(0.95):.0f}ms  p99={pct(0.99):.0f}ms  max={max(sorted_ms):.0f}ms",
            f"  statuses={self.statuses}",
        ]
        lines.extend(f"  note: {note}" for note in self.notes)
        return "\n".join(lines)


async def _timed_get(
    client: httpx.AsyncClient, url: str, timing: Timing, **kwargs: Any
) -> httpx.Response:
    start = time.perf_counter()
    response = await client.get(url, **kwargs)
    timing.record((time.perf_counter() - start) * 1000, response.status_code)
    return response


async def _timed_post(
    client: httpx.AsyncClient, url: str, timing: Timing, **kwargs: Any
) -> httpx.Response:
    start = time.perf_counter()
    response = await client.post(url, **kwargs)
    timing.record((time.perf_counter() - start) * 1000, response.status_code)
    return response


async def _create_session(client: httpx.AsyncClient) -> str:
    response = await client.post("/api/v1/sessions", json={"student_type": "freshman"})
    response.raise_for_status()
    return str(response.json()["id"])


async def bench_health(client: httpx.AsyncClient, samples: int) -> Timing:
    timing = Timing("GET /health")
    for _ in range(samples):
        await _timed_get(client, "/api/v1/health", timing)
    return timing


async def bench_retrieve(client: httpx.AsyncClient, samples: int) -> Timing:
    timing = Timing("GET /retrieve")
    for i in range(samples):
        query = QUESTIONS[i % len(QUESTIONS)]
        await _timed_get(client, "/api/v1/retrieve", timing, params={"query": query, "limit": 5})
        await asyncio.sleep(1.5)  # 40/min pace, comfortably under the 30/min limit's *ceiling*...
    return timing


async def bench_chat(client: httpx.AsyncClient, samples: int) -> Timing:
    timing = Timing("POST /chat")
    degraded = 0
    for i in range(samples):
        session_id = await _create_session(client)
        query = QUESTIONS[i % len(QUESTIONS)]
        response = await _timed_post(
            client, "/api/v1/chat", timing, json={"session_id": session_id, "message": query}
        )
        if response.status_code == 200 and "trouble generating" in response.json().get(
            "answer", ""
        ):
            degraded += 1
        await asyncio.sleep(2.5)  # stay under the 20/min limit
    if degraded:
        timing.notes.append(
            f"{degraded}/{samples} responses were the Groq-failure fallback message, not a "
            "real generation -- these numbers reflect the fast-fail path, not real Groq "
            "generation latency. Likely hitting Groq's own rate/quota limit, not this app."
        )
    return timing


async def burst_retrieve(client: httpx.AsyncClient, *, concurrency: int) -> Timing:
    """Fires `concurrency` /retrieve requests at once, bypassing the normal
    politeness pacing, to prove the rate limiter throttles a real
    concurrent burst rather than just sequential calls."""
    timing = Timing(f"GET /retrieve burst (concurrency={concurrency})")

    async def one() -> None:
        await _timed_get(
            client, "/api/v1/retrieve", timing, params={"query": "campus housing", "limit": 3}
        )

    await asyncio.gather(*(one() for _ in range(concurrency)))
    accepted = timing.statuses.get(200, 0)
    rejected = timing.statuses.get(429, 0)
    timing.notes.append(f"{accepted} accepted, {rejected} rate-limited (429)")
    return timing


async def run(args: argparse.Namespace) -> list[Timing]:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
        results = [await bench_health(client, args.health_samples)]
        results.append(await bench_retrieve(client, args.retrieve_samples))
        if not args.skip_chat:
            results.append(await bench_chat(client, args.chat_samples))

        # Let the per-minute rate-limit windows used by the sequential
        # benchmarks above fully expire before intentionally bursting past
        # the limit -- otherwise the burst test would partly be measuring
        # leftover throttling from earlier in this same run, not a clean
        # burst against a reset window.
        print("\nWaiting 60s for rate-limit windows to reset before the burst test...")
        await asyncio.sleep(60)
        results.append(await burst_retrieve(client, concurrency=args.burst_concurrency))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--health-samples", type=int, default=30)
    parser.add_argument("--retrieve-samples", type=int, default=20)
    parser.add_argument("--chat-samples", type=int, default=8)
    parser.add_argument("--burst-concurrency", type=int, default=40)
    parser.add_argument(
        "--skip-chat", action="store_true", help="Skip the Groq-backed /chat benchmark"
    )
    args = parser.parse_args()

    results = asyncio.run(run(args))

    print("\n" + "=" * 60)
    print("LOAD TEST RESULTS")
    print("=" * 60)
    for timing in results:
        print()
        print(timing.report())


if __name__ == "__main__":
    main()
