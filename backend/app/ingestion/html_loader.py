from datetime import datetime

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from app.ingestion.canonical import extract_canonical_link
from app.ingestion.cleaning import clean_text
from app.ingestion.extracted_document import ExtractedDocument, Section
from app.ingestion.timestamps import ensure_utc

_NOISE_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "svg", "form")
_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
_LAST_UPDATED_META_NAMES = ("last-modified", "revised", "date", "dcterms.modified")
_LAST_UPDATED_META_PROPERTIES = ("article:modified_time", "article:published_time")


def parse_html(html: str, *, base_url: str, fallback_title: str = "Untitled") -> ExtractedDocument:
    """Parse raw HTML into cleaned, citable text plus whatever metadata the
    page exposes. base_url is needed to resolve a <link rel="canonical">
    that uses a relative href -- always available at every call site (it's
    the URL that was just fetched to get this HTML)."""
    soup = BeautifulSoup(html, "lxml")

    # Read before _NOISE_TAGS strips <head> content -- canonical links live
    # in <head>, and "header" (a noise tag) is a *different*, unrelated
    # element (page banner chrome), but a defensive ordering here costs
    # nothing and avoids ever depending on that distinction staying true.
    canonical_url = extract_canonical_link(soup, base_url=base_url)

    for tag in soup(_NOISE_TAGS):
        tag.decompose()

    title = _extract_title(soup) or fallback_title
    text = clean_text(soup.get_text(separator="\n"))
    last_updated = ensure_utc(_extract_last_updated(soup))
    sections = _extract_sections(soup)

    return ExtractedDocument(
        title=title,
        text=text,
        last_updated=last_updated,
        canonical_url=canonical_url,
        sections=sections,
    )


def _extract_sections(soup: BeautifulSoup) -> tuple[Section, ...]:
    """DOM-order walk that segments body content at heading boundaries.

    Walks `.descendants` (not `.find_all()` per content tag) so every text
    node is captured exactly once regardless of nesting depth -- the same
    guarantee `get_text()` gives the flat `.text` field, just partitioned
    by heading instead of flattened. A text node whose nearest tag
    ancestor is a heading is skipped from body text since it's already
    captured as that heading's own title (via find_parent, not `.parent`,
    since a heading can contain inline markup like `<h2><span>A</span>
    B</h2>`).
    """
    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []

    def flush() -> None:
        text = clean_text("\n".join(current_lines))
        if text:
            sections.append(Section(heading_path=tuple(h for _, h in heading_stack), text=text))
        current_lines.clear()

    root = soup.body or soup
    for node in root.descendants:
        if isinstance(node, Tag) and node.name in _HEADING_TAGS:
            flush()
            level = int(node.name[1])
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            # Separator " ", not the default "": a heading with inline
            # markup (e.g. <h2><span>A</span> Financial Holds</h2>) has two
            # text nodes ("A", " Financial Holds") that get_text(strip=True)
            # would each strip individually and then concatenate with no
            # separator ("AFinancial Holds") -- confirmed via a failing test.
            heading_text = node.get_text(" ", strip=True)
            if heading_text:
                heading_stack.append((level, heading_text))
            continue

        if isinstance(node, NavigableString):
            if node.find_parent(_HEADING_TAGS) is not None:
                continue
            text = str(node).strip()
            if text:
                current_lines.append(text)

    flush()
    return tuple(sections)


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
