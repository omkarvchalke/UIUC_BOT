import json

from langchain_core.messages import BaseMessage

from app.core.logging import get_logger
from app.graph.generation import GeneratedAnswer, no_results_answer
from app.graph.state import RetrievedChunkState
from app.llm.groq_client import GroqClient, GroqError
from app.llm.prompt_builder import PromptBuilder
from app.models.conversation_session import StudentType

logger = get_logger(__name__)

_FALLBACK_ANSWER = (
    "I'm having trouble generating an answer right now. Please try again in a moment, or "
    "rephrase your question."
)


class GroqAnswerGenerator:
    """Real LLM generation behind the AnswerGenerator protocol from Phase 5
    -- the graph's generate_response node doesn't change at all to use this
    instead of ExtractiveAnswerGenerator."""

    def __init__(
        self, client: GroqClient | None = None, prompt_builder: PromptBuilder | None = None
    ) -> None:
        self._client = client or GroqClient()
        self._prompt_builder = prompt_builder or PromptBuilder()

    async def generate(
        self,
        query: str,
        chunks: list[RetrievedChunkState],
        *,
        context: str,
        history: list[BaseMessage],
        student_type: StudentType | None,
    ) -> GeneratedAnswer:
        if not chunks:
            return no_results_answer()

        messages = self._prompt_builder.build_messages(
            query=query, context=context, history=history, student_type=student_type
        )

        try:
            raw = await self._client.complete_json(messages)
        except GroqError as exc:
            logger.warning("groq_generation_failed", error=str(exc))
            return GeneratedAnswer(text=_FALLBACK_ANSWER, grounded=False)

        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> GeneratedAnswer:
        try:
            data = json.loads(raw)
            text = str(data["answer"])
            grounded = bool(data.get("grounded", False))
            citation_indices = [int(i) for i in data.get("citations_used", [])]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            # The model didn't follow the required JSON shape. Surface its
            # raw text rather than a generic error (it may still be a
            # usable answer), but grounded=False since we can't verify its
            # citations were real -- better to under-trust than to cite
            # sections that were never checked.
            logger.warning("groq_response_parse_failed", error=str(exc), raw=raw[:500])
            return GeneratedAnswer(text=raw, grounded=False)

        return GeneratedAnswer(text=text, grounded=grounded, citation_indices=citation_indices)
