import typing
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.core.config import get_settings

EMBEDDING_DIMENSION = 384

# BGE models are trained so that queries and passages are embedded
# asymmetrically: prefixing the *query* (never the passage) with this
# instruction measurably improves retrieval quality, per the model card.
_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


@lru_cache
def _get_model() -> SentenceTransformer:
    settings = get_settings()
    return typing.cast(
        SentenceTransformer, SentenceTransformer(settings.embedding_model_name, device="cpu")
    )


class Embedder:
    """Local, CPU-only embedding generation. No paid embedding API calls."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = _get_model()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        model = _get_model()
        vector = model.encode(
            _QUERY_INSTRUCTION + text, normalize_embeddings=True, show_progress_bar=False
        )
        return vector.tolist()
