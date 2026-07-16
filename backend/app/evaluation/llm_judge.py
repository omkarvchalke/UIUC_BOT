"""Opt-in LLM-as-judge Faithfulness scoring, using Groq. Reuses GroqClient
-- no new Groq client. Gated entirely behind --llm-judge on scripts/eval_rag.py;
never invoked from pytest or the default script run, so it never spends
Groq quota unless explicitly requested (this session has repeatedly hit
the account's daily token quota -- see app/evaluation/faithfulness.py's
docstring for why the always-on default is heuristic, not this).
"""

import json
from dataclasses import dataclass

from app.llm.groq_client import GroqClient, GroqError

_JUDGE_SYSTEM_PROMPT = (
    "You are a strict fact-checking judge. You will be given an ANSWER and a "
    "CONTEXT. Rate how well the ANSWER's claims are supported by the CONTEXT, "
    "from 0.0 (completely unsupported or fabricated) to 1.0 (every claim is "
    "fully supported by the CONTEXT). Respond with exactly this JSON object "
    'and nothing else: {"score": <float 0.0-1.0>, "reasoning": "<one sentence>"}'
)


@dataclass
class LLMJudgeResult:
    score: float
    reasoning: str


async def judge_faithfulness(groq: GroqClient, answer: str, context: str) -> LLMJudgeResult:
    messages = [
        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"CONTEXT:\n{context}\n\nANSWER:\n{answer}"},
    ]
    try:
        raw = await groq.complete_json(messages)
    except GroqError as exc:
        raise GroqError(f"LLM-judge faithfulness call failed: {exc}") from exc

    parsed = json.loads(raw)
    score = float(parsed["score"])
    return LLMJudgeResult(score=max(0.0, min(1.0, score)), reasoning=str(parsed["reasoning"]))
