#!/usr/bin/env python3
"""
Embed chunks from chunks.jsonl and store them in the local ChromaDB index.

Reads data/chunks/chunks.jsonl, embeds chunk text in batches using the
locally-running embedding model (backend/app/rag/embeddings.py — no API
key needed, see EMBEDDING_PROVIDER/EMBEDDING_MODEL in backend/.env), and
adds them to ChromaDB (backend/app/rag/vector_store.py). The index is
reset first so re-running this script always reflects the current
chunks.jsonl exactly (no stale/orphaned chunks left behind).

Usage:
    python embed_chunks.py
"""
import json
import logging
import sys
from pathlib import Path

# ingestion/embed_chunks.py -> parents[1] is the repo root
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.rag.embeddings import EmbeddingConfigError, embed_documents  # noqa: E402
from app.rag.vector_store import add_documents, reset_index  # noqa: E402

from utils import CHUNKS_DIR  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("embed_chunks")

BATCH_SIZE = 64


def load_chunks() -> list[dict]:
    chunks_path = CHUNKS_DIR / "chunks.jsonl"
    if not chunks_path.exists():
        raise FileNotFoundError(f"{chunks_path} not found. Run chunk_text.py first.")

    chunks = []
    with chunks_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))
    return chunks


def main() -> int:
    try:
        chunks = load_chunks()
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 1

    if not chunks:
        logger.warning("chunks.jsonl is empty. Nothing to embed.")
        return 0

    logger.info("Embedding %d chunk(s) into ChromaDB...", len(chunks))
    reset_index()

    embedded = 0
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c["chunk_text"] for c in batch]
        try:
            embeddings = embed_documents(texts)
        except EmbeddingConfigError as exc:
            logger.error(str(exc))
            return 1

        add_documents(batch, embeddings)
        embedded += len(batch)
        logger.info("Embedded %d/%d chunk(s)", embedded, len(chunks))

    logger.info("Done. %d chunk(s) embedded and stored in ChromaDB.", embedded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
