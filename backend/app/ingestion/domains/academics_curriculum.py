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
)
