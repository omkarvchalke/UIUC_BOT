from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Section:
    """One heading-delimited slice of a document's body text.

    heading_path is ordered outermost -> innermost (e.g. ("Registration",
    "Holds", "Financial Holds") for content under an h1>h2>h3 chain).
    Empty tuple means content before the first heading, or a page with no
    headings at all. text deliberately excludes the heading's own title
    text -- that lives in heading_path instead.
    """

    heading_path: tuple[str, ...]
    text: str


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
    # DOM-order (heading_path, text) sections, HTML only. None means "no
    # section structure available" (PDF, or any future non-HTML source) --
    # SemanticChunker degrades to flat fixed-size chunking with
    # subtopic=None in that case. Deliberately independent of `.text`:
    # `.text` stays the single flat string used for content_hash and the
    # crawler's thinness check, unaffected by this field's existence.
    sections: tuple[Section, ...] | None = None
