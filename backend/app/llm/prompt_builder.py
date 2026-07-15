from functools import lru_cache
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.models.conversation_session import StudentType

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "rag_system_prompt.txt"
_MAX_HISTORY_MESSAGES = 6


@lru_cache
def load_system_prompt() -> str:
    return _PROMPT_PATH.read_text().strip()


class PromptBuilder:
    """Builds the Groq chat message list from the graph's already-assembled
    pieces (context_builder's numbered context, the profile, recent
    history) -- deliberately reuses context_builder's [n] numbering rather
    than renumbering, since citation_generator maps the model's
    citations_used indices straight back to state["reranked_chunks"].
    """

    def __init__(self, system_prompt: str | None = None) -> None:
        self._system_prompt = system_prompt or load_system_prompt()

    def build_messages(
        self,
        *,
        query: str,
        context: str,
        history: list[BaseMessage],
        student_type: StudentType | None,
    ) -> list[dict[str, str]]:
        messages = [{"role": "system", "content": self._system_prompt}]

        for message in history[-_MAX_HISTORY_MESSAGES:]:
            if isinstance(message, HumanMessage):
                messages.append({"role": "user", "content": str(message.content)})
            elif isinstance(message, AIMessage):
                messages.append({"role": "assistant", "content": str(message.content)})

        profile_note = (
            f"The student has identified as: {student_type.value}.\n\n"
            if student_type
            else "The student's type (freshman/transfer/graduate/international) is not known.\n\n"
        )
        context_block = context if context else "(no relevant context was found)"
        user_content = f"{profile_note}Context:\n{context_block}\n\nQuestion: {query}"
        messages.append({"role": "user", "content": user_content})

        return messages
