import json
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.groq_client import GroqClient, GroqError

logger = get_logger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "query_decomposition_prompt.txt"
)


@lru_cache
def _load_system_prompt() -> str:
    return _PROMPT_PATH.read_text().strip()


def _build_messages(*, query: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _load_system_prompt()},
        {"role": "user", "content": f"Question: {query}"},
    ]


class LlmQueryDecomposer:
    """Real LLM decomposition behind the QueryDecomposer Protocol -- mirrors
    LlmRetrievalSufficiencyChecker's structure (client, JSON-mode call, a
    static _parse) closely on purpose, same fail-open shape."""

    def __init__(self, client: GroqClient | None = None) -> None:
        self._client = client or GroqClient()

    async def decompose(self, query: str) -> list[str]:
        messages = _build_messages(query=query)
        settings = get_settings()
        try:
            raw = await self._client.complete_json(
                messages,
                temperature=settings.query_decomposition_temperature,
                max_completion_tokens=settings.query_decomposition_max_completion_tokens,
            )
        except GroqError as exc:
            # Fail open: this must never break or hang the default
            # single-query experience just because Groq is down/rate-limited.
            logger.warning("query_decomposition_failed", error=str(exc))
            return [query]

        return self._parse(raw, query)

    @staticmethod
    def _parse(raw: str, original_query: str) -> list[str]:
        try:
            data = json.loads(raw)
            sub_queries = data["sub_queries"]
            if not isinstance(sub_queries, list) or not sub_queries:
                raise ValueError("sub_queries must be a non-empty list")
            cleaned = [str(q).strip() for q in sub_queries if str(q).strip()]
            if not cleaned:
                raise ValueError("sub_queries had no non-empty entries")
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            # Malformed JSON / wrong shape -- fail open to the original,
            # undecomposed question rather than lose the turn.
            logger.warning("query_decomposition_parse_failed", error=str(exc), raw=raw[:500])
            return [original_query]

        max_subqueries = get_settings().query_decomposition_max_subqueries
        return cleaned[:max_subqueries]
