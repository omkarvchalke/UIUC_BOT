import json
import re
from pathlib import Path

INGESTION_DIR = Path(__file__).resolve().parent
SOURCES_PATH = INGESTION_DIR / "sources.json"
RAW_DIR = INGESTION_DIR / "data" / "raw"
PROCESSED_DIR = INGESTION_DIR / "data" / "processed"
CHUNKS_DIR = INGESTION_DIR / "data" / "chunks"

# Identifies the bot honestly and states scope, in case a site operator inspects logs.
USER_AGENT = (
    "CampusGuideAI-Ingestion/0.1 "
    "(student portfolio project; fetches only curated public UIUC webpages; "
    "no login-protected pages are accessed)"
)


def load_sources() -> list[dict]:
    with SOURCES_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def document_id_for(source: dict) -> str:
    return f"{source['category']}__{slugify(source['title'])}"
