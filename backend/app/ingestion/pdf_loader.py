from datetime import datetime
from io import BytesIO

from pypdf import PdfReader

from app.ingestion.cleaning import clean_text
from app.ingestion.extracted_document import ExtractedDocument
from app.ingestion.timestamps import ensure_utc


def parse_pdf(pdf_bytes: bytes, *, fallback_title: str = "Untitled") -> ExtractedDocument:
    reader = PdfReader(BytesIO(pdf_bytes))

    title = _extract_title(reader) or fallback_title
    text = clean_text("\n\n".join(page.extract_text() or "" for page in reader.pages))
    last_updated = ensure_utc(_extract_last_updated(reader))

    return ExtractedDocument(title=title, text=text, last_updated=last_updated)


def _extract_title(reader: PdfReader) -> str | None:
    metadata = reader.metadata
    if metadata and metadata.title:
        return metadata.title.strip()
    return None


def _extract_last_updated(reader: PdfReader) -> datetime | None:
    metadata = reader.metadata
    if metadata is None:
        return None
    return metadata.modification_date or metadata.creation_date
