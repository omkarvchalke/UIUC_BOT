from dataclasses import dataclass

import httpx

from app.evaluation.cited_context import fetch_cited_context
from app.evaluation.faithfulness import score_faithfulness
from app.evaluation.llm_judge import LLMJudgeResult, judge_faithfulness
from app.evaluation.runner import EvalResult
from app.llm.groq_client import GroqClient


@dataclass
class FaithfulnessEvalResult:
    result: EvalResult
    heuristic_score: float | None
    llm_judge: LLMJudgeResult | None


async def run_faithfulness_all(
    base_url: str,
    eval_results: list[EvalResult],
    *,
    llm_judge: bool = False,
) -> list[FaithfulnessEvalResult]:
    """For every chat result that actually cited something, fetches the
    cited context and scores faithfulness. Results with no citations at
    all are skipped entirely -- not scored 0.0 -- since an ungrounded or
    clarification answer isn't claiming to cite anything, so "faithfulness
    to context" isn't a meaningful question for it (same edge-case
    philosophy as app/evaluation/retrieval_metrics.py's ValueError policy:
    a misleading 0.0 must not be conflated with "not applicable").
    """
    cited_results = [r for r in eval_results if r.citation_urls]
    groq = GroqClient() if llm_judge else None

    faithfulness_results: list[FaithfulnessEvalResult] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        for result in cited_results:
            context = await fetch_cited_context(
                client,
                result.case.message,
                result.citation_urls,
                student_type=result.case.student_type,
            )
            if not context:
                continue  # every cited URL failed to match -- see cited_context.py

            heuristic_score = score_faithfulness(result.answer, context)

            judge_result: LLMJudgeResult | None = None
            if llm_judge and groq is not None:
                judge_result = await judge_faithfulness(groq, result.answer, context)

            faithfulness_results.append(
                FaithfulnessEvalResult(
                    result=result, heuristic_score=heuristic_score, llm_judge=judge_result
                )
            )

    return faithfulness_results
