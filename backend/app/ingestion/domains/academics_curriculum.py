"""Academics & Curriculum -- the course catalog and academic program
structure, via the Office of the Provost."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://catalog.illinois.edu",
        department="Office of the Provost",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://catalog.illinois.edu/",
        department="Office of the Provost",
        topic=Topic.COURSE_REGISTRATION,
        source_type=SourceType.HTML,
        fallback_title="Course Catalog",
    ),
    # A live run found "how do I contact my academic advisor" got zero
    # citations and was misclassified as academic_calendar -- UIUC advising
    # is decentralized per-college with no single university-wide advising
    # office, so this points at a real college's advising page as a
    # concrete example rather than a fabricated "central advising" page.
    # fallback_title names the college explicitly so the answer doesn't
    # imply it's university-wide. Originally pointed at the College of
    # LAS's advising page (the largest college by enrollment), but that
    # domain (las.illinois.edu, Pantheon-hosted) 403s this project's
    # ingestion client specifically -- confirmed the same URL returns 200
    # via curl with an identical User-Agent, so it's a WAF-level
    # TLS/HTTP-client fingerprint block, not a UA string check, and not
    # something worth engineering around. Grainger Engineering's advising
    # page is a real, fetchable substitute.
    SourceConfig(
        url="https://grainger.illinois.edu/academics/undergraduate/advising",
        department="The Grainger College of Engineering",
        topic=Topic.ACADEMIC_ADVISING,
        source_type=SourceType.HTML,
        fallback_title="Advising (The Grainger College of Engineering)",
    ),
)
