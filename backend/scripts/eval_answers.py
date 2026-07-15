"""Run the golden-set answer-quality eval against a live backend.

Checks properties of real answers (grounded, cited, not hedging) rather
than exact wording, so it survives normal variation in Groq's phrasing
while still catching the failure modes that have actually happened: a
student-type scoped so narrowly it silently returns nothing, or a
"gateway" source so thin the model can only point back at the website
instead of answering (see app/evaluation/golden_set.py and the
sources.py comments for the real incidents each case guards against).

Requires the backend running against the real ingested corpus with a
real GROQ_API_KEY set -- this makes real Groq calls and isn't part of
the regular pytest suite (which is designed to run without a key).

Usage (from backend/):
    uv run python -m scripts.eval_answers [base_url]

Exits non-zero if any case fails.
"""

import asyncio
import sys

from app.evaluation.runner import EvalResult, run_all


def _print_report(results: list[EvalResult]) -> None:
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.case.name}")
        if not result.passed:
            for reason in result.failures:
                print(f"         - {reason}")
            print(f"         answer: {result.answer[:200]}")

    passed = sum(r.passed for r in results)
    print(f"\n{passed}/{len(results)} passed")


def main() -> int:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    results = asyncio.run(run_all(base_url))
    _print_report(results)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
