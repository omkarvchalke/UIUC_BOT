"""Run the full RAG evaluation harness against a live backend: answer-
quality PASS/FAIL (same checks as scripts/eval_answers.py), retrieval
metrics (Precision@5, Recall@5, MRR, Context Precision), Faithfulness /
Groundedness, and Latency -- one report, one run, against the same golden
set (app/evaluation/golden_set.py).

Requires the backend running against the real ingested corpus with a real
GROQ_API_KEY set -- this makes real Groq calls and isn't part of the
regular pytest suite (same as scripts/eval_answers.py).

Faithfulness is heuristic (no extra Groq calls) by default. Pass
--llm-judge for an additional, higher-fidelity Groq-based score -- this
roughly doubles the Groq calls a run makes, so use it sparingly (this
account has repeatedly hit its daily token quota this session).

Usage (from backend/):
    uv run python -m scripts.eval_rag
    uv run python -m scripts.eval_rag http://localhost:8000 --llm-judge

Exit code: non-zero only if any answer-quality case fails (same semantics
as eval_answers.py) -- retrieval metrics, faithfulness, and latency are
report-only for now; there's no historical baseline yet to set a
meaningful regression threshold against.
"""

import argparse
import asyncio

from app.evaluation.faithfulness_runner import FaithfulnessEvalResult, run_faithfulness_all
from app.evaluation.retrieval_runner import RetrievalEvalResult, run_retrieval_all
from app.evaluation.runner import EvalResult, run_all


def _print_answer_quality_report(results: list[EvalResult]) -> None:
    print("\n" + "=" * 60)
    print("ANSWER QUALITY (PASS/FAIL)")
    print("=" * 60)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.case.name}")
        if not result.passed:
            for reason in result.failures:
                print(f"         - {reason}")
            print(f"         answer: {result.answer[:200]}")

    passed = sum(r.passed for r in results)
    print(f"\n{passed}/{len(results)} passed")


def _print_retrieval_report(retrieval_results: list[RetrievalEvalResult]) -> None:
    print("\n" + "=" * 60)
    print("RETRIEVAL METRICS")
    print("=" * 60)
    if not retrieval_results:
        print("No golden-set cases have expected_relevant_urls yet -- nothing to report.")
        return

    for r in retrieval_results:
        print(
            f"{r.case.name}: Precision@5={r.precision_at_5:.2f} "
            f"Recall@5={r.recall_at_5:.2f} MRR={r.mrr:.2f} "
            f"ContextPrecision={r.context_precision:.2f}"
        )

    n = len(retrieval_results)
    print(f"\nAggregate over {n} ground-truth-bearing case(s):")
    print(f"  Precision@5      = {sum(r.precision_at_5 for r in retrieval_results) / n:.3f}")
    print(f"  Recall@5         = {sum(r.recall_at_5 for r in retrieval_results) / n:.3f}")
    print(f"  MRR              = {sum(r.mrr for r in retrieval_results) / n:.3f}")
    print(f"  Context Precision = {sum(r.context_precision for r in retrieval_results) / n:.3f}")


def _print_faithfulness_report(
    faithfulness_results: list[FaithfulnessEvalResult], *, llm_judge: bool
) -> None:
    print("\n" + "=" * 60)
    print("FAITHFULNESS / GROUNDEDNESS")
    print("=" * 60)
    print("(RAGAS treats these as near-synonymous; one scorer serves both names)")
    if not faithfulness_results:
        print("No cited answers to score.")
        return

    heuristic_scores = [
        r.heuristic_score for r in faithfulness_results if r.heuristic_score is not None
    ]
    for r in faithfulness_results:
        line = f"{r.result.case.name}: heuristic={r.heuristic_score}"
        if r.llm_judge is not None:
            line += f" llm_judge={r.llm_judge.score:.2f} ({r.llm_judge.reasoning})"
        print(line)

    if heuristic_scores:
        avg = sum(heuristic_scores) / len(heuristic_scores)
        print(f"\nAggregate heuristic Faithfulness / Groundedness = {avg:.3f}")

    if llm_judge:
        judge_scores = [r.llm_judge.score for r in faithfulness_results if r.llm_judge]
        if judge_scores:
            avg_judge = sum(judge_scores) / len(judge_scores)
            print(f"Aggregate LLM-judge Faithfulness / Groundedness = {avg_judge:.3f}")


def _print_latency_report(results: list[EvalResult]) -> None:
    print("\n" + "=" * 60)
    print("LATENCY")
    print("=" * 60)
    latencies_ms = sorted(r.latency_ms for r in results)
    if not latencies_ms:
        print("No samples.")
        return

    def pct(p: float) -> float:
        idx = min(len(latencies_ms) - 1, int(len(latencies_ms) * p))
        return latencies_ms[idx]

    avg = sum(latencies_ms) / len(latencies_ms)
    print(f"n={len(latencies_ms)}  avg={avg:.0f}ms  p50={pct(0.5):.0f}ms  p95={pct(0.95):.0f}ms")


async def _run(base_url: str, *, llm_judge: bool) -> list[EvalResult]:
    results = await run_all(base_url)
    _print_answer_quality_report(results)

    retrieval_results = await run_retrieval_all(base_url)
    _print_retrieval_report(retrieval_results)

    faithfulness_results = await run_faithfulness_all(base_url, results, llm_judge=llm_judge)
    _print_faithfulness_report(faithfulness_results, llm_judge=llm_judge)

    _print_latency_report(results)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url", nargs="?", default="http://localhost:8000")
    parser.add_argument(
        "--llm-judge",
        action="store_true",
        help="Also run an LLM-as-judge faithfulness score (extra Groq calls -- use sparingly)",
    )
    args = parser.parse_args()

    results = asyncio.run(_run(args.base_url, llm_judge=args.llm_judge))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
