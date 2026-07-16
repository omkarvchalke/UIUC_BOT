from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.llm.prompt_builder import PromptBuilder, load_system_prompt
from app.models.conversation_session import StudentType


def test_system_prompt_loads_and_is_nonempty() -> None:
    prompt = load_system_prompt()
    assert len(prompt) > 100
    assert "JSON" in prompt


def test_system_prompt_forbids_pii() -> None:
    prompt = load_system_prompt().lower()
    assert "netid" in prompt or "personally identifiable" in prompt


def test_first_message_is_system_prompt() -> None:
    builder = PromptBuilder()
    messages = builder.build_messages(
        query="What are the library hours?",
        context="[1] Library Hours (University Library):\nOpen 24/7.",
        history=[],
        student_type=None,
    )
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == load_system_prompt()


def test_user_message_includes_query_and_context() -> None:
    builder = PromptBuilder()
    messages = builder.build_messages(
        query="What are the library hours?",
        context="[1] Library Hours (University Library):\nOpen 24/7.",
        history=[],
        student_type=None,
    )
    last = messages[-1]
    assert last["role"] == "user"
    assert "What are the library hours?" in last["content"]
    assert "Library Hours" in last["content"]


def test_student_type_is_included_when_known() -> None:
    builder = PromptBuilder()
    messages = builder.build_messages(
        query="How do I apply for OPT?",
        context="[1] OPT (ISSS):\nDetails.",
        history=[],
        student_type=StudentType.INTERNATIONAL,
    )
    assert "international" in messages[-1]["content"].lower()


def test_history_is_translated_to_role_messages() -> None:
    builder = PromptBuilder()
    history = [
        HumanMessage(content="What are meal plans?"),
        AIMessage(content="Meal plans include Classic Meals [1]."),
    ]
    messages = builder.build_messages(
        query="What about for graduate students?",
        context="[1] Meal Plans (Housing):\nDetails.",
        history=history,
        student_type=None,
    )
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert messages[1]["content"] == "What are meal plans?"
    assert messages[2]["content"] == "Meal plans include Classic Meals [1]."


def test_history_is_truncated_to_recent_messages() -> None:
    builder = PromptBuilder()
    history: list[BaseMessage] = [
        HumanMessage(content=f"question {i}") if i % 2 == 0 else AIMessage(content=f"answer {i}")
        for i in range(20)
    ]
    messages = builder.build_messages(
        query="final question", context="[1] X (Y):\nZ.", history=history, student_type=None
    )
    # system + at most 6 history + final user message
    assert len(messages) <= 1 + 6 + 1


def test_empty_context_uses_placeholder() -> None:
    builder = PromptBuilder()
    messages = builder.build_messages(query="anything", context="", history=[], student_type=None)
    assert "no relevant context" in messages[-1]["content"].lower()
