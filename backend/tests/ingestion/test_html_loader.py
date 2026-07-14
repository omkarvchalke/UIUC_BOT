from datetime import UTC, datetime

from app.ingestion.html_loader import parse_html

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
    result = parse_html(_SAMPLE_HTML)
    assert result.title == "Freshman Housing Guide"


def test_extracts_main_text_and_strips_boilerplate() -> None:
    result = parse_html(_SAMPLE_HTML)
    assert "required to live in university housing" in result.text
    assert "Applications open in the spring" in result.text
    assert "tracking pixel" not in result.text
    assert "Home | Apply | Contact" not in result.text
    assert "Copyright University of Illinois" not in result.text


def test_extracts_last_updated_from_meta_tag() -> None:
    result = parse_html(_SAMPLE_HTML)
    assert result.last_updated == datetime(2026, 3, 15, 10, 0, tzinfo=UTC)


def test_missing_last_updated_returns_none() -> None:
    html = "<html><head><title>No Date</title></head><body><p>Content.</p></body></html>"
    result = parse_html(html)
    assert result.last_updated is None


def test_falls_back_to_h1_when_no_title_tag() -> None:
    html = "<html><body><h1>Fallback Heading</h1><p>Body text.</p></body></html>"
    result = parse_html(html)
    assert result.title == "Fallback Heading"


def test_falls_back_to_provided_title_when_nothing_found() -> None:
    html = "<html><body><p>Body text only.</p></body></html>"
    result = parse_html(html, fallback_title="Manifest Title")
    assert result.title == "Manifest Title"


def test_extracts_last_updated_from_time_tag() -> None:
    html = (
        "<html><head><title>T</title></head>"
        '<body><p>Text</p><time datetime="2025-11-01T00:00:00+00:00">Nov 1</time></body></html>'
    )
    result = parse_html(html)
    assert result.last_updated == datetime(2025, 11, 1, tzinfo=UTC)
