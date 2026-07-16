import asyncio
import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.core.logging import get_logger
from app.embeddings.embedder import Embedder
from app.ingestion.canonical import normalize_url
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.fetch import FetchError, build_client, fetch_response
from app.ingestion.html_loader import parse_html
from app.ingestion.robots import RobotsChecker
from app.ingestion.sources import SOURCES, SourceConfig
from app.models.conversation_session import StudentType
from app.models.document import SourceType
from app.retrieval.topic_classifier import TopicClassification, TopicClassifier

__all__ = ["Crawler", "CrawlOutcome", "CrawlSeed", "TopicClassifierLike"]


class TopicClassifierLike(Protocol):
    """Structural type for whatever classifies a topic here -- lets tests
    inject a deterministic stub instead of the real embedding model without
    Crawler depending on the concrete TopicClassifier class."""

    def classify(self, message: str) -> TopicClassification: ...


logger = get_logger(__name__)

# Below this, a page is almost certainly broken (empty body, a redirect
# stub, an error page) rather than genuinely thin-but-useful content --
# deliberately conservative. Distinguishing real "gateway" nav pages (which
# can be several thousand characters of link text) from substantive content
# turned out not to be reliable from structural signals alone (line length,
# sentence density were both tried and didn't cleanly separate known-good
# from known-bad pages); the real safety net is re-running the golden-set
# eval (app/evaluation/) after a crawl, not this filter.
MIN_CONTENT_CHARS = 500

_SKIP_EXTENSIONS = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".css", ".js",
    ".zip", ".mp3", ".mp4", ".docx", ".xlsx", ".pptx",
)  # fmt: skip
# Deliberately does NOT include .pdf: a PDF found by extension still gets
# fetched so its Content-Type is checked and it lands in the rejected list
# with a distinct "pdf (index separately)" reason (see _crawl_seed) --
# visible in a discover_sources.py report for someone to add via a PDF
# pipeline later, rather than silently vanishing the way the other skipped
# extensions do.

# URL substrings that mean "this is an auth wall, not content" -- checked
# against the *post-redirect* URL, since a login-gated page on an
# otherwise-public domain (canvas.illinois.edu, identity.uillinois.edu)
# typically redirects to an SSO/Shibboleth flow rather than 404ing or
# rejecting the request outright, so a plain HTTP-status check never sees
# it as an error.
_LOGIN_URL_MARKERS = (
    "login",
    "signin",
    "sign-in",
    "sso",
    "shibboleth",
    "saml",
    "authenticate",
    "auth/",
    # identity.uillinois.edu redirects to a URL with none of the above
    # markers (".../iamFrontEnd/iam/start") -- the domain itself is
    # nothing but an identity/auth management portal, so treating
    # "identity" as a marker is accurate here without the false-positive
    # risk a shorter token like "iam" would have (e.g. "diamond").
    "identity",
)


def _looks_like_login_page(url: str) -> bool:
    lowered = url.lower()
    return any(marker in lowered for marker in _LOGIN_URL_MARKERS)


def _is_html_content_type(content_type: str) -> bool:
    return "text/html" in content_type.lower()


# Cheap URL/title keyword signals for which StudentType a page is scoped
# to -- the same judgment call made by hand for every manifest source in
# sources.py, just automated. Falls back to the seed's own default (and
# ultimately to "applies to everyone") when nothing matches.
_STUDENT_TYPE_KEYWORDS: tuple[tuple[str, StudentType], ...] = (
    ("international", StudentType.INTERNATIONAL),
    ("transfer", StudentType.TRANSFER),
    ("graduate", StudentType.GRADUATE),
    ("freshman", StudentType.FRESHMAN),
    ("first-year", StudentType.FRESHMAN),
)


@dataclass(frozen=True)
class CrawlOutcome:
    accepted: list[SourceConfig]
    rejected: list[tuple[str, str]]  # (url, reason)
    # Cleaned-text length per accepted URL -- not needed for ingestion
    # (SourceConfig itself has everything IngestionService needs) but
    # useful for a human reviewing a discovery report to judge which pages
    # are worth keeping without re-fetching each one.
    content_chars: dict[str, int] = field(default_factory=dict)


def _extract_links(html: str, *, base_url: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    links: set[str] = set()
    for tag in soup.find_all("a", href=True):
        if not isinstance(tag, Tag):
            continue
        # .strip(): some sites (parking.illinois.edu confirmed) emit
        # href="  /about  " with stray whitespace inside the attribute --
        # unstripped, urljoin preserves it and it gets percent-encoded into
        # the URL (.../about%20%20), which 404s and wastes a page-budget
        # slot on every crawl.
        href = str(tag["href"]).strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        links.add(normalize_url(urljoin(base_url, href)))
    return links


_ERROR_PAGE_TITLE_MARKERS = ("page not found", "404 error", "not found")


def _looks_like_error_page(title: str) -> bool:
    # Several sites in this manifest return HTTP 200 with a custom "Page
    # Not Found" page instead of a real 404 status for a broken link (seen
    # on admissions.illinois.edu) -- fetch_url's raise_for_status() only
    # catches an actual error status code, so a soft-404 like this sails
    # through and, since it's mostly nav-menu chrome, is long enough to
    # clear MIN_CONTENT_CHARS too. Checked on title rather than body text:
    # the body is dominated by the same nav-menu content real pages share,
    # but the <title>/<h1> reliably says "Page Not Found" on a soft-404.
    lowered = title.lower()
    return any(marker in lowered for marker in _ERROR_PAGE_TITLE_MARKERS)


def _infer_student_types(
    url: str, title: str, default: tuple[StudentType, ...]
) -> tuple[StudentType, ...]:
    # Word-boundary match, not substring: "graduate" as a plain substring
    # also matches inside "undergraduate", which mis-tagged general/
    # freshman admissions pages (titled "..., Undergraduate Admissions,
    # ...") as graduate-only -- and since student_type is a hard retrieval
    # filter, that would have silently hidden them from freshman/transfer
    # queries. Found by inspecting a real crawl's output before trusting it.
    haystack = f"{url} {title}".lower()
    for keyword, student_type in _STUDENT_TYPE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", haystack):
            return (student_type,)
    return default


class Crawler:
    """Discovers pages under a bounded set of seeds and turns the ones that
    pass a basic quality bar into SourceConfig entries, ready to hand
    straight to IngestionService.ingest_all -- the crawler is purely a
    SourceConfig factory; fetching, chunking, and persisting still go
    through the exact same pipeline manifest sources use.
    """

    def __init__(
        self,
        *,
        politeness_delay: float = 0.5,
        min_content_chars: int = MIN_CONTENT_CHARS,
        topic_classifier: TopicClassifierLike | None = None,
        existing_urls: frozenset[str] | None = None,
    ) -> None:
        self._delay = politeness_delay
        self._min_chars = min_content_chars
        # Normalized the same way as crawled URLs (see canonical.normalize_url)
        # so a case-variant of a manifest URL is still recognized as a duplicate.
        source_urls = existing_urls if existing_urls is not None else {s.url for s in SOURCES}
        self._existing_urls = frozenset(normalize_url(u) for u in source_urls)
        # threshold=0.0: always take the best-scoring topic rather than
        # returning None below the usual 0.55 clarification threshold. That
        # threshold exists to decide whether to ask the *user* a clarifying
        # question -- it doesn't apply here, since topic on a Document is
        # metadata (used for the retrieval-debugging endpoint and manifest
        # bookkeeping only, never a hard retrieval filter -- see
        # nodes.make_retrieve_node), so a low-confidence best guess is
        # strictly better than discarding the page for want of a tag.
        self._classifier = topic_classifier or TopicClassifier(
            embedder=Embedder(), confidence_threshold=0.0
        )
        self._robots = RobotsChecker()
        # Maps a content hash to the first URL seen with that content, for
        # the lifetime of this Crawler instance (spans every seed in a
        # crawl() call). Guards against sites that serve byte-identical
        # content for many different routes -- found on map.illinois.edu, a
        # client-side-rendered app where 10 different URLs all returned the
        # same ~5000-char static shell. Without this, every route on a site
        # like that gets ingested as a separate "unique" document.
        self._content_hashes: dict[str, str] = {}
        # Maps a canonical URL (see app/ingestion/canonical.py) to the first
        # fetched URL seen with it, for the same reason and lifetime as
        # _content_hashes above -- catches the case content-hash dedup
        # can't: two different starting URLs (e.g. a tracking-param variant
        # and the plain URL) whose *rendered* HTML differs slightly (an
        # embedded nonce, a cache-buster) but which both declare the same
        # <link rel="canonical">.
        self._canonical_urls_seen: dict[str, str] = {}

    async def crawl(
        self, seeds: tuple[CrawlSeed, ...], *, client: httpx.AsyncClient | None = None
    ) -> CrawlOutcome:
        accepted: list[SourceConfig] = []
        rejected: list[tuple[str, str]] = []
        content_chars: dict[str, int] = {}
        owns_client = client is None
        http_client = client or build_client()
        try:
            for seed in seeds:
                seed_accepted, seed_rejected, seed_chars = await self._crawl_seed(seed, http_client)
                accepted.extend(seed_accepted)
                rejected.extend(seed_rejected)
                content_chars.update(seed_chars)
        finally:
            if owns_client:
                await http_client.aclose()
        return CrawlOutcome(accepted=accepted, rejected=rejected, content_chars=content_chars)

    async def _crawl_seed(
        self, seed: CrawlSeed, client: httpx.AsyncClient
    ) -> tuple[list[SourceConfig], list[tuple[str, str]], dict[str, int]]:
        accepted: list[SourceConfig] = []
        rejected: list[tuple[str, str]] = []
        content_chars: dict[str, int] = {}
        queue: list[tuple[str, int]] = [(normalize_url(seed.start_url), 0)]
        visited: set[str] = set()
        seed_domain = urlparse(seed.start_url).netloc

        while queue and len(accepted) + len(rejected) < seed.max_pages:
            url, depth = queue.pop(0)
            if url in visited or url.lower().endswith(_SKIP_EXTENSIONS):
                continue
            visited.add(url)

            if not await self._robots.is_allowed(url, client):
                rejected.append((url, "disallowed by robots.txt"))
                continue

            await asyncio.sleep(self._delay)
            try:
                response = await fetch_response(url, client=client)
            except FetchError as exc:
                rejected.append((url, f"fetch failed: {exc}"))
                continue

            final_url = str(response.url)
            if _looks_like_login_page(final_url):
                rejected.append((url, "login-gated page"))
                continue

            content_type = response.headers.get("content-type", "")
            if not _is_html_content_type(content_type):
                reason = (
                    "pdf (index separately)"
                    if "application/pdf" in content_type.lower()
                    else f"non-HTML content ({content_type.split(';')[0] or 'unknown'})"
                )
                rejected.append((url, reason))
                continue

            html = response.content.decode("utf-8", errors="replace")
            extracted = parse_html(html, base_url=final_url, fallback_title=url)
            # The URL actually stored/deduped against: the page's own
            # declared canonical link when it has one, else just the
            # (already-normalized) fetched URL. rel=canonical can only be
            # read post-fetch, so this check happens here rather than
            # alongside the pre-fetch queue/visited dedup above.
            canonical = normalize_url(extracted.canonical_url) if extracted.canonical_url else url

            if url in self._existing_urls or canonical in self._existing_urls:
                rejected.append((url, "already in the manifest"))
            elif _looks_like_error_page(extracted.title):
                rejected.append((url, "looks like a soft-404 error page"))
            elif len(extracted.text) < self._min_chars:
                rejected.append((url, f"too thin ({len(extracted.text)} chars)"))
            elif canonical in self._canonical_urls_seen:
                rejected.append(
                    (
                        url,
                        f"duplicate canonical URL (same as {self._canonical_urls_seen[canonical]})",
                    )
                )
            else:
                content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()
                duplicate_of = self._content_hashes.get(content_hash)
                if duplicate_of is not None:
                    rejected.append((url, f"duplicate content (same as {duplicate_of})"))
                else:
                    topic = self._classifier.classify(extracted.text[:2000]).topic
                    if topic is None:
                        rejected.append((url, "could not classify a topic"))
                    else:
                        self._content_hashes[content_hash] = url
                        self._canonical_urls_seen[canonical] = url
                        accepted.append(
                            SourceConfig(
                                url=canonical,
                                department=seed.department,
                                topic=topic,
                                source_type=SourceType.HTML,
                                fallback_title=extracted.title,
                                student_types=_infer_student_types(
                                    url, extracted.title, seed.default_student_types
                                ),
                            )
                        )
                        content_chars[canonical] = len(extracted.text)

            if depth >= seed.max_depth:
                continue
            for link in _extract_links(html, base_url=url):
                if (
                    link not in visited
                    and urlparse(link).netloc == seed_domain
                    and (
                        not seed.path_prefixes
                        or any(urlparse(link).path.startswith(p) for p in seed.path_prefixes)
                    )
                ):
                    queue.append((link, depth + 1))

        return accepted, rejected, content_chars
