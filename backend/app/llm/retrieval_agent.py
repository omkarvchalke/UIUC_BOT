import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.graph.retrieval_agent import SufficiencyAssessment
from app.graph.state import RetrievedChunkState
from app.llm.groq_client import GroqClient, GroqError

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "retrieval_sufficiency_prompt.txt"


@lru_cache
def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text().strip()


def _build_messages(*, query: str, context: str) -> list[dict[str, str]]:
    context_block = context if context else "(no context was retrieved)"
    user_content = f"Question: {query}\n\nContext:\n{context_block}"
    return [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": user_content},
    ]


class LlmRetrievalSufficiencyChecker:
    """Real LLM judgment behind the RetrievalSufficiencyChecker Protocol --
    mirrors GroqAnswerGenerator's structure (client, JSON-mode call, a
    static _parse) closely on purpose, same failure-handling shape."""

    def __init__(self, client: GroqClient | None = None) -> None:
        self._client = client or GroqClient()

    async def assess(
        self, *, query: str, context: str, chunks: list[RetrievedChunkState]
    ) -> SufficiencyAssessment:
        if not chunks:
            # Nothing to judge -- fail open rather than spend a Groq call
            # confirming the obvious. retrieve's own topic/student_type
            # fallbacks already tried to avoid an empty result set.
            return SufficiencyAssessment(sufficient=True, reformulated_query=None, reasoning="no_chunks")

        messages = _build_messages(query=query, context=context)
        settings = get_settings()
        try:
            raw = await self._client.complete_json(
                messages,
                temperature=settings.agentic_retrieval_temperature,
                max_completion_tokens=settings.agentic_retrieval_max_completion_tokens,
            )
        except GroqError as exc:
            # Fail open: this must never break or hang the default
            # experience just because Groq is slow, rate-limited, or down.
            logger.warning("retrieval_sufficiency_check_failed", error=str(exc))
            return SufficiencyAssessment(sufficient=True, reformulated_query=None, reasoning="groq_error")

        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> SufficiencyAssessment:
        try:
            data = json.loads(raw)
            sufficient = bool(data["sufficient"])
            reformulated = data.get("reformulated_query")
            reformulated_query = str(reformulated) if reformulated else None
            reasoning = str(data.get("reasoning", ""))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            # Malformed JSON -- fail open (treat as sufficient) rather than
            # distrust it: here "safe" means "stop looping and answer with
            # what we have", not "don't trust the citations" the way
            # GroqAnswerGenerator._parse's ungrounded fallback means.
            logger.warning("retrieval_sufficiency_parse_failed", error=str(exc), raw=raw[:500])
            return SufficiencyAssessment(sufficient=True, reformulated_query=None, reasoning="parse_error")

        return SufficiencyAssessment(
            sufficient=sufficient, reformulated_query=reformulated_query, reasoning=reasoning
        )
