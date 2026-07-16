"""Transportation & Campus Access -- parking, campus maps/building
information, and public transit serving campus, via the Parking Department,
Facilities & Services, and the Champaign-Urbana Mass Transit District."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://parking.illinois.edu",
        department="Parking Department",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        # Confirmed via an earlier crawl to be a client-side-rendered app
        # that serves the same static shell for every route -- kept in the
        # seed list per the approved-domains list, relying on Crawler's
        # duplicate-content-hash check to keep at most one copy of that
        # shell rather than hand-excluding the domain.
        start_url="https://map.illinois.edu",
        department="Facilities & Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        # Not an illinois.edu domain -- see the domain-safety allowlist in
        # tests/ingestion/test_sources.py. The actual authority for bus
        # fares/routes serving campus; illinois.edu has no equivalent.
        start_url="https://mtd.org",
        department="Champaign-Urbana Mass Transit District (MTD)",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://parking.illinois.edu/transportation",
        department="Parking Department",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Transportation",
    ),
    SourceConfig(
        url="https://parking.illinois.edu/permits",
        department="Parking Department",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Parking Permits",
    ),
    SourceConfig(
        url="https://fs.illinois.edu/campus-maps-and-building-information/",
        department="Facilities & Services",
        # Closest available fit: the page's real content is about GIS/digital
        # mapping infrastructure, not a topic this enum has a dedicated
        # bucket for.
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="Campus Maps and Building Information",
    ),
    SourceConfig(
        # Not an illinois.edu domain -- the official Champaign-Urbana Mass
        # Transit District site, which is the actual authority for bus fares
        # and routes serving campus (illinois.edu has no equivalent page of
        # its own). See the domain-safety test in test_sources.py for the
        # explicit allowlist this requires.
        url="https://mtd.org/",
        department="Champaign-Urbana Mass Transit District (MTD)",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Champaign-Urbana Mass Transit District",
    ),
)
