"""Local embeddings via sentence-transformers.

Embeddings run locally — no API key, no network call, no per-token cost —
while chat generation goes through a remote provider (Groq by default; see
app/llm/). This is a deliberate split, not an oversight: retrieval doesn't
need frontier-model quality, a good open embedding model is free and fast
on CPU, and it keeps ingestion + retrieval fully functional even with zero
LLM API credits. See README "AI Stack" for the full rationale.

EMBEDDING_PROVIDER=local is the only implementation right now — see
Known Limitations in backend/README.md if you need a remote/API-based
embedding provider instead.
"""
import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingConfigError(RuntimeError):
    """Raised when embeddings can't be generated due to missing/invalid config."""


_model = None
_loaded_model_name: Optional[str] = None


def _get_model():
    global _model, _loaded_model_name
    settings = get_settings()

    provider = settings.embedding_provider.lower().strip()
    if provider != "local":
        raise EmbeddingConfigError(
            f"EMBEDDING_PROVIDER={provider!r} is not supported yet — only "
            "'local' (sentence-transformers) is implemented."
        )

    if _model is not None and _loaded_model_name == settings.embedding_model:
        return _model

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbeddingConfigError(
            "sentence-transformers is not installed. Run "
            "`pip install -r backend/requirements.txt`."
        ) from exc

    logger.info("Loading local embedding model %r (first call only)...", settings.embedding_model)
    try:
        _model = SentenceTransformer(settings.embedding_model)
    except Exception as exc:
        # Bad model name, no network to download it the first time, corrupt
        # cache, etc. — all surface as some generic exception from the
        # underlying huggingface_hub/torch stack, so catch broadly here and
        # translate into our own clear, actionable error type.
        raise EmbeddingConfigError(
            f"Failed to load embedding model {settings.embedding_model!r}: {exc}"
        ) from exc

    _loaded_model_name = settings.embedding_model
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts. Returns one embedding vector per input text, in order."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
    return vectors.tolist()


def embed_query(text: str) -> list[float]:
    """Embed a single query string, e.g. a user's chat question."""
    return embed_documents([text])[0]
