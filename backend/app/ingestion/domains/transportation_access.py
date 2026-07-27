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
        #
        # path_prefixes restricts this to the rider-facing and
        # maps/schedules sections plus the Illinois Terminal (intercity
        # travel hub) page -- an unrestricted crawl of mtd.org's full site
        # was pulling in 6 non-English /languages/* pages (confirmed live:
        # a real "what banking options does the i-card offer" query came
        # back citing the *Chinese*-language page, since it happened to
        # rank well for an unrelated reason), plus MTD's own corporate
        # blog/HR/legal pages (/inside/advertise, /inside/board,
        # /inside/jobs, /inside/mtd-pulse and its posts, /privacy-policy,
        # /accessibility-policy) -- none of it relevant to a campus
        # assistant, all of it diluting real transit-question retrieval.
        start_url="https://mtd.org",
        department="Champaign-Urbana Mass Transit District (MTD)",
        path_prefixes=(
            "/riding",
            "/maps-and-schedules",
            "/inside/illinois-terminal",
            "/inside/contact",
        ),
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
    # A real user question found this a genuine gap: "how do I get from
    # O'Hare to campus without a car, what's cheapest" came back with a
    # driving-directions sentence and unrelated MTD/campus-shuttle content,
    # because nothing in the corpus actually covered intercity/airport
    # travel -- every other transportation source here is about parking or
    # *local* Champaign-Urbana transit. ISSS's pre-arrival page is
    # international-student-focused in its surrounding sections but this
    # specific "Getting to Champaign-Urbana" content (Willard Airport,
    # O'Hare/Midway, Amtrak, Peoria Charter bus/shuttle, Greyhound, taxi
    # cost) is equally relevant to any new student flying in -- not scoped
    # to student_types=INTERNATIONAL for that reason.
    SourceConfig(
        url="https://isss.illinois.edu/students/pre-arrival/",
        department="International Student and Scholar Services",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Getting to Champaign-Urbana (Pre-Arrival)",
    ),
)
