"""Local persistent ChromaDB vector store for CampusGuide AI chunks."""
from pathlib import Path
from typing import Any, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import get_settings

# backend/app/rag/vector_store.py -> parents[2] is backend/
BACKEND_DIR = Path(__file__).resolve().parents[2]
COLLECTION_NAME = "campusguide_chunks"


class VectorStoreConfigError(RuntimeError):
    """Raised when the configured vector store backend isn't supported."""


_client: chromadb.ClientAPI | None = None
_collection = None


def _resolve_persist_dir(configured: str) -> Path:
    """Resolve CHROMA_DB_PATH relative to backend/, not the process cwd, so
    it works the same whether invoked from backend/ (uvicorn) or ingestion/
    (embed_chunks.py)."""
    path = Path(configured)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    return path


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        settings = get_settings()
        if settings.vector_db.lower().strip() != "chromadb":
            raise VectorStoreConfigError(
                f"VECTOR_DB={settings.vector_db!r} is not supported yet — only "
                "'chromadb' is implemented."
            )
        persist_dir = _resolve_persist_dir(settings.chroma_db_path)
        persist_dir.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                chroma_product_telemetry_impl="app.rag._telemetry.NoopProductTelemetryClient",
            ),
        )
    return _client


def get_collection():
    """Get or automatically create the chunks collection."""
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def reset_index():
    """Drop and recreate the collection. Used by embed_chunks.py for a clean rebuild."""
    global _collection
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def add_documents(chunks: list[dict[str, Any]], embeddings: list[list[float]]) -> None:
    """Add (or update, by chunk_id) a batch of chunks with their embeddings."""
    if not chunks:
        return
    collection = get_collection()
    collection.upsert(
        ids=[c["chunk_id"] for c in chunks],
        embeddings=embeddings,
        documents=[c["chunk_text"] for c in chunks],
        metadatas=[
            {
                "document_id": c["document_id"],
                "source_title": c["source_title"],
                "source_url": c["source_url"],
                "category": c["category"],
                "department": c["department"],
                "chunk_index": c["chunk_index"],
            }
            for c in chunks
        ],
    )


def similarity_search(query_embedding: list[float], top_k: int = 5) -> list[dict[str, Any]]:
    """Return the top_k most similar chunks with source metadata and a similarity score."""
    collection = get_collection()
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, count),
    )

    output = []
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc_text, meta, distance in zip(documents, metadatas, distances):
        # Collection uses cosine distance (0 = identical, 2 = opposite); convert to a
        # 0-1-ish similarity score for display.
        score = max(0.0, 1 - distance)
        output.append(
            {
                "chunk_text": doc_text,
                "source_title": meta["source_title"],
                "source_url": meta["source_url"],
                "category": meta["category"],
                "department": meta["department"],
                "score": round(score, 4),
            }
        )

    return output


def lookup_source_by_title(source_title: str) -> Optional[dict[str, str]]:
    """Look up a source's current title/URL from indexed chunk metadata by
    exact source_title match — no embedding call needed, just a metadata
    filter on whatever's already been indexed.

    Used by the checklist generator (app/api/checklist.py) to pull live
    source links from the vector store rather than hardcoding URLs, so a
    changed URL in sources.json is reflected automatically after a
    re-index. Returns None if the index is empty or the title isn't
    indexed yet — callers should render the task without a source link
    rather than erroring.
    """
    collection = get_collection()
    if collection.count() == 0:
        return None

    result = collection.get(where={"source_title": source_title}, limit=1)
    metadatas = result.get("metadatas") or []
    if not metadatas:
        return None

    meta = metadatas[0]
    return {"source_title": meta["source_title"], "source_url": meta["source_url"]}
