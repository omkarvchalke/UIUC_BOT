"""Career & Employment -- job/internship search and on-campus student
employment, via The Career Center."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://careercenter.illinois.edu",
        department="The Career Center",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://handshake.illinois.edu",
        department="The Career Center",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://hireillini.illinois.edu",
        department="The Career Center",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://hireillini.illinois.edu/",
        department="The Career Center",
        topic=Topic.STUDENT_EMPLOYMENT,
        source_type=SourceType.HTML,
        fallback_title="Hire Illini",
    ),
)
