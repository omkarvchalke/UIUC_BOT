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


def test_html_comments_do_not_leak_into_extracted_text() -> None:
    # Regression test for a real bug found live: bs4's Comment is a
    # NavigableString subclass, so <!-- ... --> content (including literal
    # markup some UIUC Drupal pages put inside template-debug comments) was
    # showing up verbatim in ingested chunk content and from there in real
    # chat answers.
    html = """
    <html><body>
        <main>
            <h1>Student Code</h1>
            <!-- replace paragraph ID with an anchor ID -->
            <!-- <details id="paragraph--1508" class="paragraph paragraph--type--accordion"> -->
            <p>Decisions must be based on individual merit.</p>
        </main>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "Decisions must be based on individual merit" in result.text
    assert "paragraph--1508" not in result.text
    assert "<details" not in result.text
    assert "replace paragraph ID" not in result.text
    assert all("paragraph--" not in section.text for section in result.sections)


def test_embedded_doctype_does_not_leak_into_extracted_text() -> None:
    # Regression test for a real bug found live: a UIUC KnowledgeBase
    # article had a second, malformed "<!DOCTYPE html PUBLIC ...>" pasted
    # mid-body (an editor copy-paste artifact) -- bs4's Doctype, like
    # Comment, is a NavigableString subclass, so it leaked into a real chat
    # answer the same way.
    html = """
    <html><body>
        <main>
            <h1>IT Service Desk</h1>
            <div class="doc-body">
                <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN" "http://www.w3.org/TR/REC-html40/loose.dtd">
                Contact the IT Service Desk for help.
            </div>
        </main>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "Contact the IT Service Desk for help" in result.text


def test_ilw_header_and_footer_mega_menus_are_stripped() -> None:
    # Regression test for a real bug found live: <ilw-header>/<ilw-footer>
    # are custom elements from UIUC's shared "Illinois Web Toolkit", used
    # site-wide across the Student Affairs family of sites -- not real
    # <nav>/<header>/<footer> tags, so the plain-tag noise filtering never
    # touched them. A real document's entire first chunk was one of these
    # menus (every nav link on the site, verbatim, including "Employment"),
    # which is why many otherwise-unrelated pages on these sites kept
    # scoring high for Topic.STUDENT_EMPLOYMENT in topic classification.
    html = """
    <html><body>
        <ilw-header>
            <nav slot="links"><ul><li><a href="/hours">Hours</a></li></ul></nav>
            <ilw-header-menu>
                <ul><li><a href="/facilities">Facilities</a></li>
                <li><a href="/about/employment">Employment</a></li></ul>
            </ilw-header-menu>
        </ilw-header>
        <main>
            <h1>Campus Recreation</h1>
            <p>The ARC offers a climbing wall and an indoor pool.</p>
        </main>
        <ilw-footer>
            <nav slot="social"><ul><li><a href="#">Instagram</a></li></ul></nav>
        </ilw-footer>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "climbing wall and an indoor pool" in result.text
    assert "Employment" not in result.text
    assert "Instagram" not in result.text


def test_visually_hidden_accessibility_labels_are_stripped() -> None:
    # Regression test for a real bug found live: class="visually-hidden"
    # (and the "sr-only" convention) marks screen-reader-only accessibility
    # labels, deliberately never shown to sighted users -- but with nothing
    # filtering by CSS class, a Drupal "feature split" component's hidden
    # field-name labels ("Subtitle", "Title", "Body") were leaking into
    # extracted text ahead of the real content they labeled.
    html = """
    <html><body>
        <main>
            <div>
                <div class="visually-hidden">Subtitle</div>
                <div class="field__item">Employment</div>
            </div>
            <h2>
                <div class="visually-hidden">Title</div>
                Work Where You Play
            </h2>
            <div class="sr-only">Body</div>
            <p>Campus Recreation is one of the largest on-campus employers.</p>
        </main>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "Work Where You Play" in result.text
    assert "largest on-campus employers" in result.text
    assert "Subtitle" not in result.text
    assert "Title" not in result.text
    assert "Body" not in result.text


def test_visually_hidden_focusable_skip_link_is_stripped() -> None:
    # Regression test for a real bug found live: after the exact-token
    # ".visually-hidden" fix above, a real answer still leaked "Skip to
    # main content" -- a sitewide skip-navigation link whose class is
    # "visually-hidden-focusable skip-link ..." (visible only when
    # keyboard-focused), a real, common accessibility-utility variant that
    # an exact class-token match doesn't catch.
    html = """
    <html><body>
        <div class="visually-hidden-focusable skip-link p-3 container">
            <a href="#main-content">Skip to main content</a>
        </div>
        <main>
            <h1>Campus Recreation</h1>
            <p>The ARC offers a climbing wall and an indoor pool.</p>
        </main>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "climbing wall and an indoor pool" in result.text
    assert "Skip to main content" not in result.text
    assert "DTD HTML" not in result.text
    assert all("DTD HTML" not in section.text for section in result.sections)


def test_skip_link_with_an_unrelated_css_class_is_still_stripped() -> None:
    # Regression test for a real bug found live via a corpus audit: a
    # different UIUC site (a KnowledgeBase platform, not Drupal) uses its
    # own class="kbs-skip-link" for the identical "Skip to the main
    # content" accessibility link -- neither the visually-hidden nor the
    # skip-link CSS-class filters catch it, since it's a CMS-specific class
    # name with no shared naming convention. Matched by anchor text +
    # #-href instead, so it doesn't matter what class name a given site
    # happens to use.
    html = """
    <html><body>
        <a class="kbs-skip-link" href="#maincontent">Skip to the main content</a>
        <main>
            <h1>Answers</h1>
            <p>Contact the IT Service Desk for password resets.</p>
        </main>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "Contact the IT Service Desk" in result.text
    assert "Skip to the main content" not in result.text


def test_library_hours_js_widget_placeholder_is_stripped() -> None:
    # Regression test for a real bug found live: library.illinois.edu pages
    # embed a JS-populated "today's hours" widget (class*="UofI_Library_
    # Hours") site-wide. A static fetch never runs the JS that fills it in,
    # so the scraped text was always the literal placeholder text --
    # "Loading Library Hours..." -- which a real chat answer then cited as
    # if it were actual content.
    html = """
    <html><body>
        <main>
            <h1>Research Services</h1>
            <div class="row UofI_Library_Hours_mobile">
                <div class="UofI_Library_Hours "><div class="UofI_Library_Hours_Inner">
                Loading Library Hours...
                </div></div>
            </div>
            <p>Help with MLA, APA, and other citation styles.</p>
        </main>
    </body></html>
    """
    result = parse_html(html, base_url=_BASE_URL)
    assert "Help with MLA, APA" in result.text
    assert "Loading Library Hours" not in result.text
    assert all("Loading Library Hours" not in section.text for section in result.sections)


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


def test_inline_link_mid_sentence_does_not_shred_the_sentence() -> None:
    # Regression test for a real bug found live via a 326-question sweep:
    # a sentence containing an inline <a> link (extremely common -- "your
    # Academic College", "Student Self-Service") used to split into three
    # separate one-line "sentences" at each tag boundary ("...with your",
    # "Academic College", "."), and the extractive generator would then
    # sometimes pick the bare link text alone as if it were a complete
    # answer (e.g. "academic leave of absence" for "what's the process for
    # requesting a leave of absence?").
    html = (
        "<html><body><h1>Leaving the University</h1>"
        "<p>It is recommended you communicate your stop out plans with your "
        '<a href="/college">Academic College</a>.</p>'
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert len(result.sections) == 1
    assert result.sections[0].text == (
        "It is recommended you communicate your stop out plans with your Academic College."
    )


def test_inline_strong_mid_sentence_does_not_shred_the_sentence() -> None:
    html = "<html><body><h1>T</h1><p>Please <strong>submit</strong> the form by May 1.</p></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections[0].text == "Please submit the form by May 1."


def test_sibling_paragraphs_around_an_inline_link_stay_on_separate_lines() -> None:
    # The inline-tag grouping fix must not over-correct into gluing
    # genuinely separate block-level content together: two sibling <p>s,
    # one of which happens to contain a link, must still produce two lines.
    html = (
        "<html><body><h1>T</h1>"
        '<p>Contact your <a href="/college">Academic College</a>.</p>'
        "<p>A separate paragraph.</p>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections[0].text == "Contact your Academic College.\nA separate paragraph."


def test_table_with_header_row_formats_as_labeled_lines() -> None:
    html = (
        "<html><body><h1>Deadlines</h1>"
        "<table>"
        "<tr><th>Applicant</th><th>Deadline</th></tr>"
        "<tr><td>First-year applicants</td><td>November 1</td></tr>"
        "<tr><td>Transfer applicants</td><td>March 1</td></tr>"
        "</table>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert "First-year applicants: Deadline: November 1" in result.sections[0].text
    assert "Transfer applicants: Deadline: March 1" in result.sections[0].text


def test_table_without_header_row_falls_back_to_pipe_joined_cells() -> None:
    html = (
        "<html><body><h1>T</h1>"
        "<table><tr><td>Room 101</td><td>Available</td></tr></table>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    assert "Room 101 | Available" in result.sections[0].text


def test_table_rows_do_not_leak_into_unstructured_flat_lines() -> None:
    # Regression guard for the bug this feature replaces: without table
    # handling, each <td>'s text becomes its own unlabeled line.
    html = (
        "<html><body><h1>Deadlines</h1>"
        "<table>"
        "<tr><th>Applicant</th><th>Deadline</th></tr>"
        "<tr><td>First-year applicants</td><td>November 1</td></tr>"
        "</table>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    lines = result.sections[0].text.split("\n")
    assert "November 1" not in lines
    assert "First-year applicants" not in lines


def test_nested_table_is_not_formatted_twice() -> None:
    html = (
        "<html><body><h1>T</h1>"
        "<table><tr><td>Outer cell with "
        "<table><tr><td>Inner A</td><td>Inner B</td></tr></table>"
        "text</td><td>Second column</td></tr></table>"
        "</body></html>"
    )
    result = parse_html(html, base_url=_BASE_URL)
    # The nested table's cells are captured once, flattened, as part of the
    # outer cell's own text -- not formatted again as a second row block.
    assert result.sections[0].text.count("Inner A") == 1


def test_table_with_single_column_has_no_header_colon_prefix() -> None:
    html = "<html><body><h1>T</h1><table><tr><td>Just one column</td></tr></table></body></html>"
    result = parse_html(html, base_url=_BASE_URL)
    assert result.sections[0].text == "Just one column"
