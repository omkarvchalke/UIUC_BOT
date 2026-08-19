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
    # Replaces a previous HTML source at library.illinois.edu/library-hours/: a live
    # content-coverage audit found "What are the library hours?" dead-ending because that page
    # (and every other hours page on the domain -- Main Stacks, Rare Book & Manuscript, Media
    # Commons, SSHEL all checked) renders its hours table client-side via the same WordPress
    # widget, with only nav labels ("Email library", "Phone library", ...) in the static HTML.
    # This fetches the widget's own live JSON data source directly instead -- unit_id=80 is Main
    # Library, confirmed via libdirectory.library.illinois.edu/Api/UnitsInGateway. See
    # app/ingestion/library_hours_loader.py.
    SourceConfig(
        url="https://libdirectory.library.illinois.edu/Api/Unit/80",
        department="University Library",
        topic=Topic.LIBRARIES,
        source_type=SourceType.LIBRARY_HOURS,
        fallback_title="Main Library Hours",
    ),
)
