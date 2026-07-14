import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.models.document import DocumentChunk

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


@dataclass(frozen=True)
class BM25Result:
    chunk: DocumentChunk
    score: float


def _tokenize(text: str) -> list[str]:
    return _TOKEN_PATTERN.findall(text.lower())


class BM25Search:
    """In-memory BM25 keyword search over a chunk corpus.

    Takes the corpus in its constructor rather than fetching it itself, so
    the index can be built once (by the caller) and reused across searches
    within a request, and so tests can hand it a small fixed corpus with no
    database involved.
    """

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self._chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(chunk.content) for chunk in chunks]) if chunks else None

    def search(self, query: str, *, limit: int) -> list[BM25Result]:
        if self._bm25 is None:
            return []

        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(
            zip(self._chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True
        )
        return [
            BM25Result(chunk=chunk, score=float(score))
            for chunk, score in ranked[:limit]
            if score > 0
        ]
