from bs4 import BeautifulSoup

from app.ingestion.canonical import extract_canonical_link, normalize_url


def test_lowercases_scheme_host_path() -> None:
    assert normalize_url("HTTPS://Example.ILLINOIS.edu/Apply/Freshman") == (
        "https://example.illinois.edu/apply/freshman"
    )


def test_strips_trailing_slash() -> None:
    assert normalize_url("https://example.illinois.edu/apply/") == (
        "https://example.illinois.edu/apply"
    )


def test_strips_fragment() -> None:
    assert normalize_url("https://example.illinois.edu/apply#steps") == (
        "https://example.illinois.edu/apply"
    )


def test_leaves_genuinely_meaningful_query_params_untouched() -> None:
    # A course catalog search or filtered event list is a *different* page
    # per query value -- only the tracking-param allowlist gets stripped,
    # not the query string as a whole.
    url = "https://example.illinois.edu/search?term=chemistry&department=chem"
    assert normalize_url(url) == url


def test_strips_tracking_query_params() -> None:
    url = "https://example.illinois.edu/apply?utm_source=email&utm_campaign=fall2026&fbclid=abc123"
    assert normalize_url(url) == "https://example.illinois.edu/apply"


def test_strips_only_tracking_params_keeps_the_rest() -> None:
    url = "https://example.illinois.edu/search?term=chemistry&utm_source=email"
    assert normalize_url(url) == "https://example.illinois.edu/search?term=chemistry"


def test_two_case_variant_urls_normalize_to_the_same_value() -> None:
    a = normalize_url("https://example.illinois.edu/Apply/Freshman/Process")
    b = normalize_url("https://example.illinois.edu/apply/freshman/process")
    assert a == b


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def test_extracts_absolute_canonical_href() -> None:
    html = (
        '<html><head><link rel="canonical" href="https://example.illinois.edu/real"></head></html>'
    )
    result = extract_canonical_link(_soup(html), base_url="https://example.illinois.edu/dupe")
    assert result == "https://example.illinois.edu/real"


def test_resolves_relative_canonical_href_against_base_url() -> None:
    html = '<html><head><link rel="canonical" href="/real"></head></html>'
    result = extract_canonical_link(
        _soup(html), base_url="https://example.illinois.edu/nested/dupe"
    )
    assert result == "https://example.illinois.edu/real"


def test_no_canonical_link_returns_none() -> None:
    html = "<html><head><title>No canonical here</title></head></html>"
    assert extract_canonical_link(_soup(html), base_url="https://example.illinois.edu/x") is None


def test_ignores_non_canonical_rel_links() -> None:
    # A <link rel="stylesheet"> or rel="icon" shouldn't be mistaken for a
    # canonical declaration just because some other <link> tag exists.
    html = (
        '<html><head><link rel="stylesheet" href="/style.css">'
        '<link rel="icon" href="/favicon.ico"></head></html>'
    )
    assert extract_canonical_link(_soup(html), base_url="https://example.illinois.edu/x") is None
