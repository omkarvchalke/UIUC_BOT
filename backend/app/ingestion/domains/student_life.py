"""Student Life & Organizations -- student government, registered student
organizations, and campus involvement, via Student Affairs and the Illini
Union."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://studentaffairs.illinois.edu",
        department="Student Affairs",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://union.illinois.edu",
        department="Illini Union",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://studentengagement.illinois.edu/soda/studentorgs/registration",
        department="Student Engagement",
        topic=Topic.STUDENT_ORGANIZATIONS,
        source_type=SourceType.HTML,
        fallback_title="Student Org Registration",
    ),
)
