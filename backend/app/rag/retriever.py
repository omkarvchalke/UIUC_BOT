"""Retrieval layer: turns a user question into the top-k most relevant chunks."""
from app.rag.embeddings import embed_query
from app.rag.vector_store import similarity_search

DEFAULT_TOP_K = 5


def retrieve(question: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """Embed the question and return the top_k most similar chunks.

    Returns an empty list if the vector store has no chunks indexed yet.
    Raises EmbeddingConfigError (from app.rag.embeddings) if the embedding
    model/provider is misconfigured — callers are expected to translate
    that into a clear API error rather than a raw stack trace.
    """
    query_embedding = embed_query(question)
    return similarity_search(query_embedding, top_k=top_k)
