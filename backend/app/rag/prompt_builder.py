"""Builds the chat-completion messages sent to the generation model.

Sources (title/url/category/department) are never requested from the model —
they're attached programmatically from retrieved-chunk metadata (see
app/api/chat.py). This is a deliberate defense-in-depth measure on top of
the prompt's "do not invent URLs" rule: the model literally never has the
opportunity to author a source URL.

Two output-format modes share the same base rules (rag_system_prompt.txt,
rules 1-8) but end with a different final instruction:
  - JSON mode: used by the non-streaming answer call and the metadata
    follow-up call (generator.generate_answer / generate_metadata).
  - Plain-text mode: used by the streaming answer call
    (generator.generate_answer_stream) — JSON and token-by-token streaming
    don't mix well (you can't usefully render partial JSON), so the
    streamed call asks for prose only, and a small separate JSON call
    determines next_steps/grounded afterward once the full answer is known.
"""
from pathlib import Path

# backend/app/rag/prompt_builder.py -> parents[1] is backend/app/
PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "rag_system_prompt.txt"

NO_CONTEXT_PLACEHOLDER = "(No relevant public source content was found for this question.)"

JSON_MODE_INSTRUCTION = (
    "Respond with a single JSON object and nothing else — no markdown, no "
    "code fences, no commentary outside the JSON. The object must have "
    'exactly these three keys:\n'
    '- "answer": a string with the direct answer and a brief supporting '
    "explanation, grounded only in the retrieved context.\n"
    '- "next_steps": an array of short, concrete next-step strings (an '
    "empty array is fine if there are none).\n"
    '- "grounded": true if the retrieved context actually contains '
    "information that answers the question, false if the context does not "
    "address the question at all (e.g., it's about an unrelated topic). "
    'Be honest here even when "answer" has to say the context doesn\'t '
    "cover it."
)

PLAIN_TEXT_INSTRUCTION = (
    "Respond with plain text only: just the direct answer and a brief "
    "supporting explanation, grounded only in the retrieved context. Do "
    "not use JSON, markdown code fences, headers, or any other "
    "formatting — plain prose only, since this response is streamed to "
    "the user as you write it and must be readable at every point along "
    "the way."
)


def load_base_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_context_block(chunks: list[dict]) -> str:
    if not chunks:
        return NO_CONTEXT_PLACEHOLDER

    parts = []
    for idx, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{idx}] Source: {chunk['source_title']} ({chunk['category']})\n{chunk['chunk_text']}"
        )
    return "\n\n".join(parts)


def build_user_message(question: str, chunks: list[dict]) -> str:
    context = build_context_block(chunks)
    return f"Question:\n{question}\n\nRetrieved Context:\n{context}"


def build_history_messages(history: list[dict] | None) -> list[dict]:
    """Turn prior conversation turns (from ChatRequest.history) into chat
    messages inserted between the system prompt and the current question.
    Each turn is just its original {role, content} — we don't re-inject
    retrieved context for historical turns, only for the current one, to
    keep the prompt from growing unbounded across a long conversation."""
    if not history:
        return []
    return [{"role": turn["role"], "content": turn["content"]} for turn in history]


def build_messages(
    question: str, chunks: list[dict], history: list[dict] | None = None
) -> list[dict]:
    """JSON-mode messages — non-streaming answer generation and the
    metadata-only follow-up call both use this."""
    return (
        [{"role": "system", "content": f"{load_base_system_prompt()}\n\n{JSON_MODE_INSTRUCTION}"}]
        + build_history_messages(history)
        + [{"role": "user", "content": build_user_message(question, chunks)}]
    )


def build_stream_messages(
    question: str, chunks: list[dict], history: list[dict] | None = None
) -> list[dict]:
    """Plain-text-mode messages — the streaming answer call uses this."""
    return (
        [{"role": "system", "content": f"{load_base_system_prompt()}\n\n{PLAIN_TEXT_INSTRUCTION}"}]
        + build_history_messages(history)
        + [{"role": "user", "content": build_user_message(question, chunks)}]
    )
