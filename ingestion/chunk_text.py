#!/usr/bin/env python3
"""
Split cleaned processed text into metadata-rich, overlapping chunks.

Reads data/processed/<document_id>.txt + matching .meta.json, splits each
document into ~500-800 token chunks (character-based approximation, ~4
chars/token) with ~100 token overlap, and writes every chunk as one JSON
line to data/chunks/chunks.jsonl. Documents with no readable text are
logged and skipped rather than aborting the run.

Usage:
    python chunk_text.py
"""
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from utils import CHUNKS_DIR, PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("chunk_text")

# Token counts are approximated at ~4 characters/token (no tokenizer dependency).
CHARS_PER_TOKEN = 4
TARGET_TOKENS = 650  # within the requested 500-800 token range
OVERLAP_TOKENS = 100
CHUNK_SIZE_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = OVERLAP_TOKENS * CHARS_PER_TOKEN


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            # Snap the boundary back to the nearest whitespace so we don't cut mid-word.
            snap = max(text.rfind(" ", start, end), text.rfind("\n", start, end))
            if snap > start:
                end = snap

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break

        next_start = max(end - overlap, start + 1)  # always make forward progress
        # If the overlap step landed mid-word, skip forward to the next word boundary.
        if not text[next_start - 1].isspace() and not text[next_start].isspace():
            ws = text.find(" ", next_start)
            nl = text.find("\n", next_start)
            candidates = [c for c in (ws, nl) if c != -1]
            if candidates:
                next_start = min(candidates) + 1
        start = next_start

    return chunks


def process_one(meta_path: Path, created_at: str) -> list[dict]:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    document_id = meta["document_id"]

    text_path = PROCESSED_DIR / f"{document_id}.txt"
    if not text_path.exists():
        logger.warning("Processed text missing for %s, skipping.", document_id)
        return []

    text = text_path.read_text(encoding="utf-8")
    pieces = split_into_chunks(text)

    if not pieces:
        logger.warning("No text to chunk for %s, skipping.", document_id)
        return []

    records = []
    for idx, chunk_text_value in enumerate(pieces):
        records.append(
            {
                "chunk_id": f"{document_id}__{idx:04d}",
                "document_id": document_id,
                "source_title": meta["title"],
                "source_url": meta["url"],
                "category": meta["category"],
                "department": meta["department"],
                "chunk_text": chunk_text_value,
                "chunk_index": idx,
                "created_at": created_at,
            }
        )

    logger.info("Chunked %s -> %d chunk(s)", document_id, len(records))
    return records


def main() -> int:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

    meta_files = sorted(PROCESSED_DIR.glob("*.meta.json"))
    if not meta_files:
        logger.error("No processed documents found in %s. Run clean_text.py first.", PROCESSED_DIR)
        return 1

    created_at = datetime.now(timezone.utc).isoformat()

    all_chunks: list[dict] = []
    skipped = 0
    documents_processed = 0

    for meta_path in meta_files:
        records = process_one(meta_path, created_at)
        if records:
            documents_processed += 1
            all_chunks.extend(records)
        else:
            skipped += 1

    chunks_path = CHUNKS_DIR / "chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for record in all_chunks:
            f.write(json.dumps(record) + "\n")

    logger.info(
        "Done. %d document(s) processed, %d chunk(s) created, %d document(s) skipped.",
        documents_processed,
        len(all_chunks),
        skipped,
    )
    logger.info("Chunks written to %s", chunks_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
