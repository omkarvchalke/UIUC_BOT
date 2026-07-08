#!/usr/bin/env python3
"""
Clean raw HTML saved by fetch_pages.py into readable plain text.

Reads data/raw/<document_id>.meta.json + matching .html and writes
data/processed/<document_id>.txt plus updated metadata. Pages that failed
to fetch, or fail to parse, are skipped with a warning rather than aborting
the run.

Extraction strategy: many university pages don't wrap their nav menus in
semantic <nav>/<footer> tags, so naive tag-stripping leaves mostly menu
links behind. We try trafilatura's main-content extraction first (it uses
text-density heuristics, not just tag names) and fall back to manual
BeautifulSoup boilerplate-stripping if trafilatura returns too little text.

Usage:
    python clean_text.py
"""
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup

from utils import PROCESSED_DIR, RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clean_text")

NOISE_TAGS = [
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "aside",
    "noscript",
    "form",
    "iframe",
    "svg",
]

# Below this many characters, trafilatura's extraction is treated as too thin
# to trust and we fall back to the manual BeautifulSoup pass instead.
MIN_TRAFILATURA_CHARS = 200


def normalize_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def extract_with_beautifulsoup(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag_name in NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    return normalize_whitespace(soup.get_text(separator="\n"))


def clean_html(html: str) -> str:
    extracted = trafilatura.extract(html, favor_recall=True, include_tables=True)
    if extracted and len(extracted.strip()) >= MIN_TRAFILATURA_CHARS:
        return normalize_whitespace(extracted)
    return extract_with_beautifulsoup(html)


def process_one(meta_path: Path) -> dict | None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not meta.get("success"):
        logger.info("Skipping %s (fetch was not successful).", meta["document_id"])
        return None

    document_id = meta["document_id"]
    html_path = RAW_DIR / f"{document_id}.html"
    if not html_path.exists():
        logger.warning("Raw HTML missing for %s, skipping.", document_id)
        return None

    html = html_path.read_text(encoding="utf-8")
    try:
        clean = clean_html(html)
    except Exception as exc:  # keep the pipeline resilient to malformed HTML
        logger.warning("Failed to clean %s: %s", document_id, exc)
        return None

    if not clean:
        logger.warning("No readable text extracted for %s, skipping.", document_id)
        return None

    text_path = PROCESSED_DIR / f"{document_id}.txt"
    text_path.write_text(clean, encoding="utf-8")

    processed_meta = {
        **meta,
        "cleaned_at": datetime.now(timezone.utc).isoformat(),
        "char_count": len(clean),
    }
    processed_meta_path = PROCESSED_DIR / f"{document_id}.meta.json"
    processed_meta_path.write_text(json.dumps(processed_meta, indent=2), encoding="utf-8")

    logger.info("Cleaned %s -> %s (%d chars)", document_id, text_path.name, len(clean))
    return processed_meta


def main() -> int:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    meta_files = sorted(RAW_DIR.glob("*.meta.json"))
    if not meta_files:
        logger.error("No raw metadata found in %s. Run fetch_pages.py first.", RAW_DIR)
        return 1

    results = []
    for meta_path in meta_files:
        result = process_one(meta_path)
        if result:
            results.append(result)

    manifest_path = PROCESSED_DIR / "processed_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    logger.info("Done. %d of %d raw pages cleaned successfully.", len(results), len(meta_files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
