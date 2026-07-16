"""Libraries & Research -- library hours, services, and research support,
via the University Library."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        # JS-rendered for anything dynamic (see README's Content coverage
        # section) -- kept anyway since static pages elsewhere on the site
        # (policies, service descriptions) may still have real content.
        start_url="https://library.illinois.edu",
        department="University Library",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://www.library.illinois.edu/library-hours/",
        department="University Library",
        topic=Topic.LIBRARIES,
        source_type=SourceType.HTML,
        fallback_title="Library Hours",
    ),
)
