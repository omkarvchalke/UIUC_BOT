#!/usr/bin/env python3
"""
Run the full ingestion pipeline end-to-end: fetch -> clean -> chunk -> embed.

Stops immediately if any step fails (non-zero exit code), leaving whatever
earlier steps already produced on disk untouched.

Usage:
    python refresh_index.py
"""
import logging
import sys

import chunk_text
import clean_text
import embed_chunks
import fetch_pages

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("refresh_index")

STEPS = [
    ("fetch_pages", fetch_pages.main),
    ("clean_text", clean_text.main),
    ("chunk_text", chunk_text.main),
    ("embed_chunks", embed_chunks.main),
]


def main() -> int:
    for name, step in STEPS:
        logger.info("=== Running %s ===", name)
        exit_code = step()
        if exit_code != 0:
            logger.error("%s failed (exit code %d). Stopping pipeline.", name, exit_code)
            return exit_code

    logger.info("=== Full index refresh complete ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
