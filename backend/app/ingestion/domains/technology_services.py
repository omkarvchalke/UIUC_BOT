"""Technology Services -- university IT services, identity/authentication,
the help-desk knowledge base, Canvas, the campus mobile app, and the
university webstore, via Technology Services and the University of Illinois
Webstore."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://techservices.illinois.edu",
        department="Technology Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://identity.uillinois.edu",
        department="Technology Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://answers.uillinois.edu",
        department="Technology Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://canvas.illinois.edu",
        department="Technology Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://webstore.illinois.edu",
        department="University of Illinois Webstore",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://app.illinois.edu",
        department="Technology Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://www.techservices.illinois.edu/",
        department="Technology Services",
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="Technology Services",
    ),
    SourceConfig(
        url="https://webstore.illinois.edu/home/",
        department="University of Illinois Webstore",
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="University of Illinois Webstore",
    ),
)
