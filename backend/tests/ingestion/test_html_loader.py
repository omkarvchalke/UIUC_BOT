from datetime import UTC, datetime

from app.ingestion.extracted_document import Section
from app.ingestion.html_loader import parse_html

_BASE_URL = "https://example.illinois.edu/page"

_SAMPLE_HTML = """
<html>
<head>
    <title>Freshman Housing Guide</title>
    <meta name="last-modified" content="2026-03-15T10:00:00+00:00">
    <script>console.log("tracking pixel");</script>
    <style>.hidden { display: none; }</style>
</head>
<body>
    <nav>Home | Apply | Contact</nav>
    <main>
        <h1>Freshman Housing Guide</h1>
        <p>All incoming freshmen are required to live in university housing.</p>
        <p>Applications open in the spring for the following fall semester.</p>
    </main>
    <footer>Copyright University of Illinois</footer>
</body>
</html>
"""


def test_extracts_title_from_title_tag() -> None:
    result = parse_html(_SAMPLE_HTML, base_url=_BASE_URL)
    assert result.title == "Freshman Housing Guide"


def test_extracts_main_text_and_strips_boilerplate() -> None:
    result = parse_html(_SAMPLE_HTML, base_url=_BASE_URL)
    assert "required to live in university housing" in result.text
    assert "Applications open in the spring" in result.text
    assert "tracking pixel" not in result.text
    assert "Home | Apply | Contact" not in result.text
    assert "Copyright University of Illinois" not in result.text


def test_extracts_last_updated_from_meta_tag() -> None:
    result = parse_html(_SAMPLE_HTML, base_url=_BASE_URL)
    assert result.last_updated == datetime(2026, 3, 15, 10, 0, tzinfo=UTC)


def test_missing_last_updated_returns_none() -> None:
    html = "<html><head><title>No Date</title></head><body><p>Content.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.last_updated is None


def test_falls_back_to_h1_when_no_title_tag() -> None:
    html = "<html><body><h1>Fallback Heading</h1><p>Body text.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.title == "Fallback Heading"


def test_falls_back_to_provided_title_when_nothing_found() -> None:
    html = "<html><body><p>Body text only.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL, fallback_title="Manifest Title")
    assert result.title == "Manifest Title"


def test_extracts_last_updated_from_time_tag() -> None:
    html = (
        "<html><head><title>T</title></head>"
        '<body><p>Text</p><time datetime="2025-11-01T00:00:00+00:00">Nov 1</time></body></html>'
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert result.last_updated == datetime(2025, 11, 1, tzinfo=UTC)


def test_extracts_absolute_canonical_link() -> None:
    html = (
        "<html><head><title>T</title>"
        '<link rel="canonical" href="https://example.illinois.edu/real-page">'
        "</head><body><p>Text</p></body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert result.canonical_url == "https://example.illinois.edu/real-page"


def test_resolves_relative_canonical_link_against_base_url() -> None:
    html = (
        '<html><head><title>T</title><link rel="canonical" href="/real-page"></head>'
        "<body><p>Text</p></body></html>"
    )
    result = parse_html(html, base_url="https://example.illinois.edu/some/nested/path")
    assert result.canonical_url == "https://example.illinois.edu/real-page"


def test_no_canonical_link_returns_none() -> None:
    result = parse_html(_SAMPLE_HTML, base_url=_BASE_URL)
    assert result.canonical_url is None


def test_extracts_single_section_under_one_heading() -> None:
    html = "<html><body><h1>Registration</h1><p>How to register for classes.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections == (
        Section(heading_path=("Registration",), text="How to register for classes."),
    )


def test_nested_headings_stack_into_heading_path() -> None:
    html = (
        "<html><body>"
        "<h1>Registration</h1><p>Overview text.</p>"
        "<h2>Holds</h2><p>Holds text.</p>"
        "<h3>Financial Holds</h3><p>Financial holds text.</p>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections == (
        Section(heading_path=("Registration",), text="Overview text."),
        Section(heading_path=("Registration", "Holds"), text="Holds text."),
        Section(
            heading_path=("Registration", "Holds", "Financial Holds"),
            text="Financial holds text.",
        ),
    )


def test_heading_level_jump_pops_stack_correctly() -> None:
    # h1 -> h3 directly (skipping h2): the stack should still pop down to
    # "shallower than 3" (i.e. drop nothing, since h1 < h3) and push h3 on
    # top of h1, not silently drop the h1 ancestor.
    html = (
        "<html><body>"
        "<h1>Registration</h1><p>Overview.</p>"
        "<h3>Financial Holds</h3><p>Details.</p>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections == (
        Section(heading_path=("Registration",), text="Overview."),
        Section(heading_path=("Registration", "Financial Holds"), text="Details."),
    )


def test_content_before_first_heading_has_empty_heading_path() -> None:
    html = "<html><body><p>Lead-in text.</p><h1>Registration</h1><p>Body.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections[0] == Section(heading_path=(), text="Lead-in text.")


def test_inline_markup_inside_heading_does_not_leak_into_following_section() -> None:
    html = "<html><body><h2><span>A</span> Financial Holds</h2><p>Body text.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections == (Section(heading_path=("A Financial Holds",), text="Body text."),)


def test_empty_heading_tag_does_not_push_onto_stack() -> None:
    html = "<html><body><h1></h1><p>Body under no real heading.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections == (Section(heading_path=(), text="Body under no real heading."),)


def test_page_with_no_headings_yields_single_section() -> None:
    html = "<html><body><p>Just body text, no headings at all.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections == (
        Section(heading_path=(), text="Just body text, no headings at all."),
    )


def test_flat_text_field_is_unaffected_by_sections() -> None:
    result = parse_html(_SAMPLE_HTML, base_url=_BASE_URL)
    assert "required to live in university housing" in result.text
    assert result.sections is not None and len(result.sections) > 0
