import json

import pytest

from app.core.config import get_settings
from app.llm.groq_client import GroqClient

pytestmark = pytest.mark.skipif(
    not get_settings().groq_api_key, reason="GROQ_API_KEY not configured"
)


async def test_complete_json_returns_valid_json() -> None:
    client = GroqClient()
    messages = [
        {
            "role": "system",
            "content": ('Respond with exactly this JSON object and nothing else: {"answer": "ok"}'),
        },
        {"role": "user", "content": "test"},
    ]

    raw = await client.complete_json(messages)

    data = json.loads(raw)
    assert "answer" in data


async def test_complete_json_follows_rag_system_prompt_format() -> None:
    from app.llm.prompt_builder import PromptBuilder

    builder = PromptBuilder()
    messages = builder.build_messages(
        query="What are the library hours?",
        context=(
            "[1] Library Hours (University Library):\n"
            "The main library is open 24/7 during finals week."
        ),
        history=[],
        student_type=None,
    )

    client = GroqClient()
    raw = await client.complete_json(messages)
    data = json.loads(raw)

    assert "answer" in data
    assert "grounded" in data
    assert "citations_used" in data
    assert isinstance(data["citations_used"], list)
