from datetime import datetime

from bs4 import BeautifulSoup, Tag

from app.ingestion.cleaning import clean_text
from app.ingestion.extracted_document import ExtractedDocument
from app.ingestion.timestamps import ensure_utc

_NOISE_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "svg", "form")
_LAST_UPDATED_META_NAMES = ("last-modified", "revised", "date", "dcterms.modified")
_LAST_UPDATED_META_PROPERTIES = ("article:modified_time", "article:published_time")


def parse_html(html: str, *, fallback_title: str = "Untitled") -> ExtractedDocument:
    """Parse raw HTML into cleaned, citable text plus whatever metadata the page exposes."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    title = _extract_title(soup) or fallback_title
    text = clean_text(soup.get_text(separator="\n"))
    last_updated = ensure_utc(_extract_last_updated(soup))

    return ExtractedDocument(title=title, text=text, last_updated=last_updated)


def _extract_title(soup: BeautifulSoup) -> str | None:
    if soup.title and soup.title.string:
        return soup.title.string.strip()

    h1 = soup.find("h1")
    if isinstance(h1, Tag):
        text = h1.get_text(strip=True)
        if text:
            return text

    return None


def _extract_last_updated(soup: BeautifulSoup) -> datetime | None:
    for meta_name in _LAST_UPDATED_META_NAMES:
        tag = soup.find("meta", attrs={"name": meta_name})
        if isinstance(tag, Tag) and (content := tag.get("content")):
            if parsed := _parse_datetime(str(content)):
                return parsed

    for meta_property in _LAST_UPDATED_META_PROPERTIES:
        tag = soup.find("meta", attrs={"property": meta_property})
        if isinstance(tag, Tag) and (content := tag.get("content")):
            if parsed := _parse_datetime(str(content)):
                return parsed

    time_tag = soup.find("time")
    if isinstance(time_tag, Tag) and (datetime_attr := time_tag.get("datetime")):
        if parsed := _parse_datetime(str(datetime_attr)):
            return parsed

    return None


def _parse_datetime(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
