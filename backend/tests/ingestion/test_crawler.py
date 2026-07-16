import httpx

from app.ingestion.crawler import Crawler, CrawlSeed
from app.models.conversation_session import StudentType
from app.models.document import Topic
from app.retrieval.topic_classifier import TopicClassification

# Comfortably over Crawler's default MIN_CONTENT_CHARS (500).
_SUBSTANTIAL_TEXT = "Freshmen live in undergraduate residence halls near the quad. " * 15
_THIN_TEXT = "Apply Now"


class _StubClassifier:
    """Deterministic stand-in for the real embedding-based classifier --
    these tests exercise crawl logic (link discovery, filtering, student
    type inference), not the embedding model."""

    def classify(self, message: str) -> TopicClassification:
        return TopicClassification(topic=Topic.HOUSING, confidence=0.9)


def _page(
    title: str, body: str, links: tuple[str, ...] = (), *, canonical: str | None = None
) -> bytes:
    link_html = "".join(f'<a href="{href}">link</a>' for href in links)
    canonical_html = f'<link rel="canonical" href="{canonical}">' if canonical else ""
    return (
        f"<html><head><title>{title}</title>{canonical_html}</head>"
        f"<body>{body}{link_html}</body></html>"
    ).encode()


def _site(pages: dict[str, bytes], robots: str | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        if path in pages:
            return httpx.Response(
                200, content=pages[path], headers={"content-type": "text/html; charset=utf-8"}
            )
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def _crawler(**overrides: object) -> Crawler:
    defaults: dict[str, object] = {
        "politeness_delay": 0,
        "topic_classifier": _StubClassifier(),
        "existing_urls": frozenset(),
    }
    defaults.update(overrides)
    return Crawler(**defaults)  # type: ignore[arg-type]


async def test_discovers_linked_pages_within_path_prefix() -> None:
    pages = {
        "/apply": _page("Apply Hub", _SUBSTANTIAL_TEXT, links=("/apply/steps", "/news/unrelated")),
        "/apply/steps": _page("Steps", _SUBSTANTIAL_TEXT),
        "/news/unrelated": _page("News", _SUBSTANTIAL_TEXT),
    }
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/apply",
        department="Test Dept",
        path_prefixes=("/apply",),
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    urls = {s.url for s in outcome.accepted}
    assert urls == {
        "https://example.illinois.edu/apply",
        "https://example.illinois.edu/apply/steps",
    }


async def test_does_not_follow_links_off_domain() -> None:
    pages = {
        "/apply": _page("Apply Hub", _SUBSTANTIAL_TEXT, links=("https://other.edu/page",)),
    }
    seed = CrawlSeed(start_url="https://example.illinois.edu/apply", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert all("other.edu" not in s.url for s in outcome.accepted)


async def test_respects_max_depth() -> None:
    pages = {
        "/a": _page("A", _SUBSTANTIAL_TEXT, links=("/b",)),
        "/b": _page("B", _SUBSTANTIAL_TEXT, links=("/c",)),
        "/c": _page("C", _SUBSTANTIAL_TEXT),
    }
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/a", department="Test Dept", max_depth=1
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    urls = {s.url for s in outcome.accepted}
    assert urls == {"https://example.illinois.edu/a", "https://example.illinois.edu/b"}


async def test_respects_max_pages() -> None:
    pages = {
        "/a": _page("A", _SUBSTANTIAL_TEXT, links=("/b", "/c", "/d")),
        "/b": _page("B", _SUBSTANTIAL_TEXT),
        "/c": _page("C", _SUBSTANTIAL_TEXT),
        "/d": _page("D", _SUBSTANTIAL_TEXT),
    }
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/a", department="Test Dept", max_pages=2
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert len(outcome.accepted) + len(outcome.rejected) == 2


async def test_rejects_pages_already_in_the_manifest() -> None:
    pages = {"/a": _page("A", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(start_url="https://example.illinois.edu/a", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler(existing_urls=frozenset({"https://example.illinois.edu/a"})).crawl(
            (seed,), client=client
        )

    assert outcome.accepted == []
    assert outcome.rejected == [("https://example.illinois.edu/a", "already in the manifest")]


async def test_rejects_pages_below_min_content_chars() -> None:
    pages = {"/a": _page("A", _THIN_TEXT)}
    seed = CrawlSeed(start_url="https://example.illinois.edu/a", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted == []
    assert "too thin" in outcome.rejected[0][1]


async def test_respects_robots_txt_disallow() -> None:
    pages = {
        "/a": _page("A", _SUBSTANTIAL_TEXT, links=("/private/b",)),
        "/private/b": _page("B", _SUBSTANTIAL_TEXT),
    }
    seed = CrawlSeed(start_url="https://example.illinois.edu/a", department="Test Dept")
    robots = "User-agent: *\nDisallow: /private/\n"
    async with httpx.AsyncClient(transport=_site(pages, robots=robots)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    urls = {s.url for s in outcome.accepted}
    assert "https://example.illinois.edu/private/b" not in urls


async def test_infers_student_type_from_url_keyword() -> None:
    pages = {"/apply/transfer/dates": _page("Transfer Dates", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/apply/transfer/dates", department="Test Dept"
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted[0].student_types == (StudentType.TRANSFER,)


async def test_falls_back_to_seed_default_student_types() -> None:
    pages = {"/students/orientation": _page("Orientation", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/students/orientation",
        department="Test Dept",
        default_student_types=(StudentType.INTERNATIONAL,),
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted[0].student_types == (StudentType.INTERNATIONAL,)


async def test_assigns_topic_from_classifier() -> None:
    pages = {"/a": _page("A", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(start_url="https://example.illinois.edu/a", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted[0].topic is Topic.HOUSING


async def test_reports_content_char_count_for_accepted_pages() -> None:
    pages = {"/a": _page("A", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(start_url="https://example.illinois.edu/a", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    # >= not ==: the page <title> text is also part of the extracted body
    # text (html_loader.py doesn't strip <title>/<head>), so a few extra
    # characters beyond the body content itself are expected.
    assert outcome.content_chars["https://example.illinois.edu/a"] >= len(_SUBSTANTIAL_TEXT)


async def test_does_not_mistake_undergraduate_for_graduate_keyword() -> None:
    # Regression test: a page titled "..., Undergraduate Admissions, ..."
    # was getting tagged student_types=(GRADUATE,) because "graduate" is a
    # substring of "undergraduate" -- found via a real crawl before this
    # fix, where it silently hid several freshman-facing pages from
    # freshman/transfer queries (student_type is a hard retrieval filter).
    pages = {
        "/apply": _page(
            "Apply, Undergraduate Admissions, University of Illinois", _SUBSTANTIAL_TEXT
        )
    }
    seed = CrawlSeed(start_url="https://example.illinois.edu/apply", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted[0].student_types == ()


async def test_treats_differently_cased_manifest_url_as_a_duplicate() -> None:
    # Regression test: illinois.edu sites are served case-insensitively, so
    # a crawled /apply/freshman/process was not recognized as the same page
    # as a manually-curated /Apply/Freshman/process already in the
    # manifest, and got re-ingested as a "new" duplicate with independently
    # (and incorrectly) inferred metadata.
    pages = {"/apply/freshman/process": _page("Process", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/apply/freshman/process", department="Test Dept"
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler(
            existing_urls=frozenset({"https://example.illinois.edu/Apply/Freshman/Process"})
        ).crawl((seed,), client=client)

    assert outcome.accepted == []
    assert outcome.rejected[0][1] == "already in the manifest"


async def test_rejects_soft_404_pages() -> None:
    # Regression test: admissions.illinois.edu returns HTTP 200 with a
    # custom "Page Not Found" page for a broken link -- fetch_url's
    # raise_for_status() only catches a real error status code, and the
    # page's nav-menu chrome is long enough to clear MIN_CONTENT_CHARS, so
    # it was getting ingested as if it were real content.
    pages = {"/apply/nondegree": _page("Page Not Found, Illinois Admissions", _SUBSTANTIAL_TEXT)}
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/apply/nondegree", department="Test Dept"
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted == []
    assert outcome.rejected[0][1] == "looks like a soft-404 error page"


async def test_rejects_pages_that_redirect_to_a_login_wall() -> None:
    # Regression case: housing.illinois.edu/dining is a real public link
    # that redirects to /user/login?destination=/dining for an
    # unauthenticated request -- a plain HTTP-status check sees this as a
    # normal 200 (the login *page* itself loads fine), so the redirect
    # target has to be checked against login-URL markers.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/dining":
            return httpx.Response(302, headers={"location": "/user/login?destination=/dining"})
        if request.url.path == "/user/login":
            return httpx.Response(
                200,
                content=_page("Login", _SUBSTANTIAL_TEXT),
                headers={"content-type": "text/html"},
            )
        return httpx.Response(404)

    seed = CrawlSeed(start_url="https://example.illinois.edu/dining", department="Test Dept")
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted == []
    assert outcome.rejected == [("https://example.illinois.edu/dining", "login-gated page")]


async def test_rejects_non_html_content_with_a_distinct_reason_for_pdfs() -> None:
    # PDFs (and any other non-HTML response, e.g. a JSON API) shouldn't be
    # run through the HTML parser -- and per the "index separately"
    # requirement, a PDF specifically needs its own recognizable reason so
    # it's visible in a discovery report rather than lumped in with
    # ordinary rejections.
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/handbook.pdf":
            return httpx.Response(
                200, content=b"%PDF-1.4 fake", headers={"content-type": "application/pdf"}
            )
        return httpx.Response(404)

    seed = CrawlSeed(start_url="https://example.illinois.edu/handbook.pdf", department="Test Dept")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert outcome.accepted == []
    assert outcome.rejected == [
        ("https://example.illinois.edu/handbook.pdf", "pdf (index separately)")
    ]


async def test_strips_whitespace_from_link_hrefs() -> None:
    # Regression case: parking.illinois.edu emits href="  /about  " with
    # stray whitespace inside the attribute -- left unstripped, urljoin
    # preserves it and it gets percent-encoded into the URL
    # (.../about%20%20), which 404s and silently wastes a page-budget slot
    # on every crawl instead of reaching the real page.
    pages = {
        "/a": _page("A", _SUBSTANTIAL_TEXT, links=("  /about  ",)),
        "/about": _page("About", _SUBSTANTIAL_TEXT),
    }
    seed = CrawlSeed(start_url="https://example.illinois.edu/a", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    urls = {s.url for s in outcome.accepted}
    assert "https://example.illinois.edu/about" in urls
    assert all("%20" not in url for url in urls)


async def test_rejects_duplicate_content_served_at_a_different_url() -> None:
    # Regression case: map.illinois.edu is a client-side-rendered app that
    # serves the exact same static shell HTML for every route -- without
    # this check, each route gets ingested as a separate "unique" document.
    # /a and /b deliberately have no links to each other (a link's visible
    # anchor text would make the two pages' extracted text differ) --
    # instead a third hub page links to both, and /a/ /b share identical
    # bodies.
    pages = {
        "/hub": _page("Hub", _SUBSTANTIAL_TEXT, links=("/a", "/b")),
        "/a": _page("Shell", _SUBSTANTIAL_TEXT),
        "/b": _page("Shell", _SUBSTANTIAL_TEXT),
    }
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/hub", department="Test Dept", max_depth=2
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    accepted_urls = {s.url for s in outcome.accepted}
    assert "https://example.illinois.edu/hub" in accepted_urls
    # Link-discovery order between /a and /b isn't guaranteed (a set), so
    # exactly one of them is accepted -- which one wins isn't the point.
    shell_urls = {"https://example.illinois.edu/a", "https://example.illinois.edu/b"}
    assert len(accepted_urls & shell_urls) == 1
    duplicate_reasons = [r for _, r in outcome.rejected if r.startswith("duplicate content")]
    assert len(duplicate_reasons) == 1


async def test_accepted_source_uses_the_declared_canonical_url() -> None:
    pages = {
        "/tracked-link": _page(
            "Real Page", _SUBSTANTIAL_TEXT, canonical="https://example.illinois.edu/real-page"
        ),
    }
    seed = CrawlSeed(start_url="https://example.illinois.edu/tracked-link", department="Test Dept")
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    assert len(outcome.accepted) == 1
    assert outcome.accepted[0].url == "https://example.illinois.edu/real-page"


async def test_rejects_a_second_url_with_the_same_canonical_as_an_already_accepted_page() -> None:
    # Two distinct starting URLs whose HTML happens to differ slightly (a
    # cache-buster, an embedded nonce -- simulated here as different visible
    # text) but which both declare the same canonical link are the same
    # document; content-hash dedup alone wouldn't catch this since the raw
    # text genuinely differs.
    pages = {
        "/hub": _page("Hub", _SUBSTANTIAL_TEXT, links=("/variant-a", "/variant-b")),
        "/variant-a": _page(
            "Variant A",
            _SUBSTANTIAL_TEXT + " Some page-specific noise A.",
            canonical="https://example.illinois.edu/real-page",
        ),
        "/variant-b": _page(
            "Variant B",
            _SUBSTANTIAL_TEXT + " Some different page-specific noise B.",
            canonical="https://example.illinois.edu/real-page",
        ),
    }
    seed = CrawlSeed(
        start_url="https://example.illinois.edu/hub", department="Test Dept", max_depth=2
    )
    async with httpx.AsyncClient(transport=_site(pages)) as client:
        outcome = await _crawler().crawl((seed,), client=client)

    accepted_urls = {s.url for s in outcome.accepted}
    assert "https://example.illinois.edu/real-page" in accepted_urls
    assert len([u for u in accepted_urls if u == "https://example.illinois.edu/real-page"]) == 1
    canonical_duplicate_reasons = [
        r for _, r in outcome.rejected if r.startswith("duplicate canonical URL")
    ]
    assert len(canonical_duplicate_reasons) == 1
