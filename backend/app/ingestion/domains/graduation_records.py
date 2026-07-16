"""Graduation & Records -- commencement and the campus bookstore, via the
Office of the Registrar and the Illini Union Bookstore."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://commencement.illinois.edu",
        department="Office of the Registrar",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://bookstore.illinois.edu",
        department="Illini Union Bookstore",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://commencement.illinois.edu/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR,
        source_type=SourceType.HTML,
        fallback_title="Illinois Commencement",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/",
        department="Illini Union Bookstore",
        # No clean topical fit (retail, not a service category this enum
        # covers) -- STUDENT_ORGANIZATIONS is the least-wrong bucket among
        # "general campus life" topics.
        topic=Topic.STUDENT_ORGANIZATIONS,
        source_type=SourceType.HTML,
        fallback_title="Illini Union Bookstore",
    ),
)
