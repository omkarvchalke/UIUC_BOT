from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExtractedDocument:
    title: str
    text: str
    last_updated: datetime | None
    # The page's own <link rel="canonical"> target (HTML only -- PDFs have
    # no such concept, so this is always None for a PDF-sourced document).
    # None means "no canonical link declared"; the caller falls back to the
    # fetched URL in that case (see app/ingestion/canonical.py).
    canonical_url: str | None = None
