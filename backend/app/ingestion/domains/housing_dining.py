"""Housing & Dining -- residence halls, applying for housing, move-in, meal
plans, and dining costs, via University Housing."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://housing.illinois.edu",
        department="University Housing",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://housing.illinois.edu/living-communities/halls/undergraduate",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="Undergraduate Halls",
        student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    SourceConfig(
        url="https://housing.illinois.edu/dine/meal-plans/meal-plans",
        department="University Housing",
        topic=Topic.DINING,
        source_type=SourceType.HTML,
        fallback_title="Meal Plans",
    ),
    # The following was checked individually via WebFetch against a larger
    # candidate list (~20 URLs from a hand-compiled domain list) -- most of
    # that list turned out to be thin nav hubs, login-gated portals, or dead
    # links; only a handful had real substantive content worth adding.
    SourceConfig(
        url="https://housing.illinois.edu/Apply/New-Resident/How-To-Apply",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="New Resident: How to Apply",
    ),
    SourceConfig(
        url="https://housing.illinois.edu/MyHousing/Move-In",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="Fall Move-In",
    ),
    # The following was checked against a ~100-URL hand-compiled list
    # spanning many additional departments (banking, bursar, safety,
    # bookstore, etc.). Most of that list was either already covered, dead
    # links, login-gated, or thin nav hubs -- these had real substantive
    # content.
    SourceConfig(
        url="https://www.housing.illinois.edu/dine/purchase",
        department="University Housing",
        topic=Topic.DINING,
        source_type=SourceType.HTML,
        fallback_title="Purchasing Illini Cash and Meal Plans",
    ),
    SourceConfig(
        url="https://www.housing.illinois.edu/cost",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="Costs",
    ),
)
