#!/usr/bin/env python3
"""
Fetch curated public UIUC webpages listed in sources.json.

Saves raw HTML to data/raw/<document_id>.html and per-page metadata to
data/raw/<document_id>.meta.json. A failed URL is logged and skipped —
it never stops the rest of the pipeline.

Usage:
    python fetch_pages.py
"""
import json
import logging
import sys
from datetime import datetime, timezone

import requests

from utils import RAW_DIR, USER_AGENT, document_id_for, load_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_pages")

TIMEOUT_SECONDS = 15
HEADERS = {"User-Agent": USER_AGENT}


def fetch_one(source: dict) -> dict:
    document_id = document_id_for(source)
    url = source["url"]

    meta = {
        "document_id": document_id,
        "title": source["title"],
        "category": source["category"],
        "department": source["department"],
        "url": url,
        "source_type": source.get("source_type", "official_public_webpage"),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "success": False,
        "http_status": None,
        "content_length": 0,
        "error": None,
    }

    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
        meta["http_status"] = response.status_code
        response.raise_for_status()

        html_path = RAW_DIR / f"{document_id}.html"
        html_path.write_text(response.text, encoding="utf-8")

        meta["success"] = True
        meta["content_length"] = len(response.text)
        logger.info("Fetched %s (%d bytes) -> %s", url, meta["content_length"], html_path.name)
    except requests.RequestException as exc:
        meta["error"] = str(exc)
        logger.warning("Failed to fetch %s: %s", url, exc)

    meta_path = RAW_DIR / f"{document_id}.meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    logger.info("Fetching %d curated public source(s)...", len(sources))

    results = [fetch_one(source) for source in sources]

    manifest_path = RAW_DIR / "fetch_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    succeeded = sum(1 for r in results if r["success"])
    failed = len(results) - succeeded
    logger.info("Done. %d succeeded, %d failed.", succeeded, failed)
    if failed:
        logger.warning(
            "Failed URLs (see data/raw/*.meta.json for details): %s",
            ", ".join(r["url"] for r in results if not r["success"]),
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
