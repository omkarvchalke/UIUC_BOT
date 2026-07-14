import typing
from functools import lru_cache
from typing import TypeVar

from sentence_transformers import CrossEncoder

# A small (~80MB), CPU-friendly cross-encoder. Cross-encoders score a
# (query, passage) pair jointly through one transformer forward pass rather
# than comparing two independently-computed embeddings (what the bi-encoder
# semantic search in Phase 4 does), which makes them meaningfully more
# accurate for final ranking -- standard practice in production RAG
# pipelines, and why "Re-ranker" is its own stage distinct from
# "Hybrid Search" in the spec's graph rather than redundant with it.
_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

T = TypeVar("T")


@lru_cache
def _get_model() -> CrossEncoder:
    return typing.cast(CrossEncoder, CrossEncoder(_MODEL_NAME, device="cpu"))


class CrossEncoderReranker:
    """Generic over the candidate's payload type: takes (text, payload)
    pairs and returns them reordered with a score, rather than being
    coupled to any one "chunk" dataclass -- the graph node passes its own
    RetrievedChunkState dicts through untouched instead of having to
    reconstruct a different type just to satisfy this class's signature.
    """

    def rerank(
        self, query: str, candidates: list[tuple[str, T]], *, top_k: int
    ) -> list[tuple[T, float]]:
        if not candidates:
            return []

        model = _get_model()
        pairs = [(query, text) for text, _ in candidates]
        # CrossEncoder.predict's stub covers a much broader multimodal input
        # union than the plain (str, str) pairs this always passes; verified
        # correct at runtime (see the interactive check during development).
        scores = model.predict(pairs)  # type: ignore[arg-type]

        ranked = sorted(
            zip(candidates, scores, strict=True), key=lambda pair: pair[1], reverse=True
        )
        return [(payload, float(score)) for (_, payload), score in ranked[:top_k]]
