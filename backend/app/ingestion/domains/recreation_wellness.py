"""Recreation & Wellness -- campus recreation facilities/membership, student
health services and insurance, and counseling, via Campus Recreation,
McKinley Health Center, Student Health Insurance, and the Counseling
Center."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://campusrec.illinois.edu",
        department="Campus Recreation",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://mckinley.illinois.edu",
        department="McKinley Health Center",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://si.illinois.edu",
        department="Student Health Insurance",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://counselingcenter.illinois.edu",
        department="Counseling Center",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://campusrec.illinois.edu/membership",
        department="Campus Recreation",
        topic=Topic.CAMPUS_RECREATION,
        source_type=SourceType.HTML,
        fallback_title="Membership",
    ),
    SourceConfig(
        url="https://mckinley.illinois.edu/fees/health-service-fee",
        department="McKinley Health Center",
        topic=Topic.HEALTH_INSURANCE,
        source_type=SourceType.HTML,
        fallback_title="Health Service Fee",
    ),
    SourceConfig(
        url="https://counselingcenter.illinois.edu/",
        department="Counseling Center",
        # No dedicated "mental health" topic exists in this enum; HEALTH_INSURANCE
        # is the closest fit and already covers McKinley Health Center's
        # health-service content for the same reason.
        topic=Topic.HEALTH_INSURANCE,
        source_type=SourceType.HTML,
        fallback_title="Counseling Center",
    ),
    SourceConfig(
        url="https://campusrec.illinois.edu/facilities",
        department="Campus Recreation",
        topic=Topic.CAMPUS_RECREATION,
        source_type=SourceType.HTML,
        fallback_title="Facilities",
    ),
)
