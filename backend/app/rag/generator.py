"""Provider-agnostic chat generation for RAG answers.

Delegates the actual API call to whichever provider LLM_PROVIDER selects
(see app/llm/provider_factory.py) — this module doesn't know or care
whether that's Groq, OpenAI, Google, or OpenRouter. It only owns: building
the prompt, parsing the JSON response, and the raw-text fallback.

Three entry points:
  - generate_answer(): single non-streaming call, used by POST /api/chat.
  - generate_answer_stream(): plain-text streaming call, used by
    POST /api/chat/stream for the token-by-token answer.
  - generate_metadata(): a small follow-up JSON call made *after* a stream
    completes, to get next_steps/grounded once the full answer text is
    known (see prompt_builder.py module docstring for why streaming and
    JSON mode are split into two calls instead of one).
"""
import json
import logging
from typing import Iterator

from app.llm.base import LLMProviderError
from app.llm.provider_factory import get_llm_client
from app.rag.prompt_builder import build_messages, build_stream_messages

logger = logging.getLogger(__name__)

METADATA_REQUEST = (
    "Based on your answer above and the retrieved context, respond with a "
    "single JSON object and nothing else — no markdown, no code fences. "
    'The object must have exactly these two keys:\n'
    '- "next_steps": an array of short, concrete next-step strings (an '
    "empty array is fine if there are none).\n"
    '- "grounded": true if the retrieved context actually contains '
    "information that answers the question, false if the context does not "
    "address the question at all. Do not repeat or modify your answer — "
    "respond with JSON only."
)


class GenerationConfigError(RuntimeError):
    """Raised when generation can't proceed due to missing/invalid config."""


def _parse_metadata(raw_content: str) -> dict:
    parsed = json.loads(raw_content)
    next_steps = [str(s).strip() for s in parsed.get("next_steps", []) if str(s).strip()]
    grounded = bool(parsed.get("grounded", True))
    return {"next_steps": next_steps, "grounded": grounded}


def generate_answer(question: str, chunks: list[dict], history: list[dict] | None = None) -> dict:
    """Call the configured LLM provider and return
    {"answer": str, "next_steps": list[str], "grounded": bool}.

    Confidence and source citations are computed elsewhere (app/api/chat.py)
    from retrieval metadata, not trusted from the model — this function's
    only job is the natural-language answer, next steps, and a self-reported
    "grounded" flag. `grounded` is a narrow, downward-only signal (see
    app/api/chat.py): the model can tell us it *didn't* find the answer in
    the context, which forces confidence down, but it can never claim high
    confidence or author a source itself.

    If the model doesn't return valid JSON (a formatting slip, or a
    provider/model that doesn't support JSON mode), falls back to using the
    raw text as the answer rather than raising — a parsing hiccup should
    never surface as a 500 to the user. `grounded` defaults to True in that
    case since we have no signal either way and don't want to punish a
    provider that just doesn't speak JSON mode.
    """
    messages = build_messages(question, chunks, history)

    try:
        client = get_llm_client()
        raw_content = client.generate(messages, json_mode=True)
    except LLMProviderError as exc:
        raise GenerationConfigError(str(exc)) from exc

    try:
        parsed = json.loads(raw_content)
        answer = str(parsed.get("answer", "")).strip()
        next_steps = [str(s).strip() for s in parsed.get("next_steps", []) if str(s).strip()]
        grounded = bool(parsed.get("grounded", True))
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Model returned non-JSON output, falling back to raw text: %s", exc)
        answer = raw_content.strip()
        next_steps = []
        grounded = True

    if not answer:
        answer = (
            "I don't have enough public-source information to answer this confidently. "
            "Please contact the relevant university office for official guidance."
        )
        grounded = False

    return {"answer": answer, "next_steps": next_steps, "grounded": grounded}


def generate_answer_stream(
    question: str, chunks: list[dict], history: list[dict] | None = None
) -> Iterator[str]:
    """Yield the answer as plain-text chunks as they arrive from the model.

    Unlike generate_answer(), this never returns next_steps/grounded — call
    generate_metadata() with the accumulated answer once the stream ends.
    """
    messages = build_stream_messages(question, chunks, history)
    try:
        client = get_llm_client()
        yield from client.generate_stream(messages)
    except LLMProviderError as exc:
        raise GenerationConfigError(str(exc)) from exc


def generate_metadata(question: str, chunks: list[dict], answer: str) -> dict:
    """Follow-up JSON-mode call made after a streamed answer is complete;
    returns {"next_steps": list[str], "grounded": bool}.

    Reuses the same JSON-mode messages as generate_answer() so the model has
    the same context, then appends the already-streamed answer plus a
    request for just the two metadata fields — the model is not asked to
    reproduce the answer.
    """
    messages = build_messages(question, chunks) + [
        {"role": "assistant", "content": answer},
        {"role": "user", "content": METADATA_REQUEST},
    ]

    try:
        client = get_llm_client()
        raw_content = client.generate(messages, json_mode=True)
    except LLMProviderError as exc:
        raise GenerationConfigError(str(exc)) from exc

    try:
        return _parse_metadata(raw_content)
    except (json.JSONDecodeError, AttributeError) as exc:
        logger.warning("Metadata call returned non-JSON output, defaulting: %s", exc)
        return {"next_steps": [], "grounded": True}
