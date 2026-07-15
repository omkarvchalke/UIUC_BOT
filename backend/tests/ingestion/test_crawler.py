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


def _page(title: str, body: str, links: tuple[str, ...] = ()) -> bytes:
    link_html = "".join(f'<a href="{href}">link</a>' for href in links)
    return (
        f"<html><head><title>{title}</title></head><body>{body}{link_html}</body></html>".encode()
    )


def _site(pages: dict[str, bytes], robots: str | None = None) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/robots.txt":
            return httpx.Response(200, text=robots) if robots else httpx.Response(404)
        if path in pages:
            return httpx.Response(200, content=pages[path])
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
