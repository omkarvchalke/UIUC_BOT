from datetime import datetime

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PreformattedString

from app.ingestion.canonical import extract_canonical_link
from app.ingestion.cleaning import clean_text
from app.ingestion.extracted_document import ExtractedDocument, Section
from app.ingestion.timestamps import ensure_utc

_NOISE_TAGS = (
    "script",
    "style",
    "nav",
    "footer",
    "header",
    "noscript",
    "svg",
    "form",
    # <ilw-header>/<ilw-footer>: custom elements from UIUC's shared
    # "Illinois Web Toolkit" (cdn.toolkit.illinois.edu), used site-wide
    # across the Student Affairs family of sites (Campus Recreation, The
    # Career Center, University Housing, Illini Union, McKinley Health
    # Center, ISSS, the Registrar, ...). Not real <nav>/<header> tags, so
    # the plain-tag noise filtering above never touched them -- confirmed
    # live, a document's *entire first chunk* was this menu (every nav
    # link on the site, verbatim, including "Employment"), which is why so
    # many otherwise-unrelated pages on these sites kept scoring high for
    # Topic.STUDENT_EMPLOYMENT: this menu, not the page's real content, was
    # dominating both its embedding and a big chunk of what actually got
    # cited to users.
    "ilw-header",
    "ilw-footer",
)
_HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
# Tags that sit *inside* a sentence rather than marking a real content
# boundary -- text under one of these must stay on the same line as its
# surrounding prose, not start a new one. Confirmed live via a 326-question
# sweep: a sentence like "...communicate your stop out plans with your
# Academic College." routinely has "Academic College" as its own <a> link,
# which the old per-text-node line-splitting below turned into three
# separate one-line "sentences" ("...with your", "Academic College", "."),
# each short enough to look like a real, complete answer on its own to the
# extractive generator -- producing answers that were just a bare link
# label ("academic leave of absence") or a truncated fragment ("Download
# software from the") instead of the real sentence they were cut from.
_INLINE_TAGS = frozenset(
    {
        "a",
        "span",
        "strong",
        "em",
        "b",
        "i",
        "u",
        "sup",
        "sub",
        "small",
        "mark",
        "abbr",
        "cite",
        "q",
        "time",
        "code",
        "kbd",
        "var",
        "samp",
        "label",
        "s",
        "strike",
        "wbr",
        "ins",
        "del",
        "font",
        "big",
        "tt",
        "bdi",
        "bdo",
    }
)
_LAST_UPDATED_META_NAMES = ("last-modified", "revised", "date", "dcterms.modified")
_LAST_UPDATED_META_PROPERTIES = ("article:modified_time", "article:published_time")
_SKIP_LINK_PHRASES = frozenset(
    {
        "skip to main content",
        "skip to the main content",
        "skip to content",
        "skip navigation",
        "skip to navigation",
    }
)


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

    # class="visually-hidden" (and the "sr-only" convention some other
    # UIUC sites use): screen-reader-only accessibility labels, deliberately
    # never shown to sighted users -- but with nothing filtering by CSS
    # class, they were included in extracted text same as real content.
    # Confirmed live on a Drupal "feature split" component: a sighted user
    # sees "Employment / Work Where You Play / Campus Recreation is one of
    # the largest on-campus employers...", but the extracted text also
    # picked up the hidden field-name labels around it ("Subtitle" before
    # "Employment", "Title" before "Work Where You Play", "Body" before the
    # real paragraph) -- this is the source of the "Student Affairs
    # University Housing Body ..." -style prefix noise seen in several real
    # chat answers.
    #
    # Substring match ([class*=...]), not an exact class token
    # (.visually-hidden): a real answer still leaked "Skip to main content"
    # after the exact-token version of this fix, from a sitewide skip-nav
    # link whose class is "visually-hidden-focusable skip-link ..." -- a
    # real, common accessibility-utility variant (visible only when
    # keyboard-focused) that ".visually-hidden" alone doesn't match since
    # "visually-hidden-focusable" is one hyphenated token, not two classes.
    for hidden in soup.select('[class*="visually-hidden"], [class*="sr-only"]'):
        hidden.decompose()

    # class*="UofI_Library_Hours": a JS-populated "today's hours" widget
    # embedded site-wide across library.illinois.edu pages (a static fetch
    # never runs the JS that fills it in, so the scraped text is always the
    # literal placeholder, "Loading Library Hours..."). Confirmed live: a
    # real chat answer to "Library hours" cited this placeholder text
    # itself as if it were an answer -- worse than the already-documented
    # "hours aren't captured" gap, since it looks like real, confident
    # content instead of an honest decline.
    for widget in soup.select('[class*="UofI_Library_Hours"]'):
        widget.decompose()

    # Skip-navigation links, matched semantically (an internal #anchor jump
    # whose text is one of the handful of standard skip-link phrasings)
    # rather than by CSS class: confirmed live that chasing class names
    # site-by-site doesn't scale -- "Skip to the main content" survived the
    # visually-hidden-focusable fix above because a *different* UIUC site
    # (a KnowledgeBase platform, not Drupal) uses its own unrelated
    # class="kbs-skip-link" for the identical accessibility pattern.
    for link in soup.select('a[href^="#"]'):
        text = link.get_text(strip=True).lower()
        if text in _SKIP_LINK_PHRASES:
            link.decompose()

    # bs4's Comment/Doctype/CData/ProcessingInstruction/Declaration are all
    # NavigableString subclasses (via the common PreformattedString base),
    # so their raw markup -- angle brackets and all -- is included verbatim
    # by _extract_sections' descendants walk unless stripped first (soup.
    # get_text() below already excludes them on its own). Confirmed live,
    # two separate real cases: several UIUC Drupal pages embed
    # template-debug comments like "<!-- replace paragraph ID with an
    # anchor ID --> <!-- <details id="paragraph--1508" class="..."> -->",
    # and one KnowledgeBase article had a second, malformed
    # "<!DOCTYPE html PUBLIC ...>" pasted mid-body (an editor copy-paste
    # artifact) -- both leaked that literal markup into real ingested chunk
    # content and from there into real chat answers.
    for node in soup.find_all(string=lambda text: isinstance(text, PreformattedString)):
        node.extract()

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


def _nearest_line_ancestor(node: NavigableString) -> Tag | None:
    """Walks up past inline tags (a, span, strong, ...) to find the tag that
    actually marks a real line boundary for this text node. Two text nodes
    that resolve to the *same* ancestor here belong on the same line/
    sentence, even if one of them sits inside an inline tag -- e.g. both
    "...with your " and "Academic College" in "...with your <a>Academic
    College</a>." resolve to the same enclosing <p>, so they're joined into
    one line instead of the link text becoming its own line."""
    parent = node.parent
    while isinstance(parent, Tag) and parent.name in _INLINE_TAGS:
        parent = parent.parent
    return parent if isinstance(parent, Tag) else None


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

    Text nodes are grouped into lines by their nearest *non-inline*
    ancestor (see _nearest_line_ancestor), not one line per text node --
    otherwise a sentence containing an inline tag (a link, a <strong>) gets
    shredded into several one-line fragments at every tag boundary, and a
    plain nav link's anchor text ("Academic College") ends up looking like
    its own short, complete "sentence" instead of the two or three words it
    actually is in the middle of a real one.
    """
    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []
    current_line_parts: list[str] = []
    current_line_ancestor: Tag | None = None

    def flush_line() -> None:
        nonlocal current_line_ancestor
        if current_line_parts:
            current_lines.append(" ".join(current_line_parts))
            current_line_parts.clear()
        current_line_ancestor = None

    def flush() -> None:
        flush_line()
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
            if not text:
                continue
            ancestor = _nearest_line_ancestor(node)
            if current_line_parts and ancestor is not current_line_ancestor:
                flush_line()
            current_line_ancestor = ancestor
            current_line_parts.append(text)

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
