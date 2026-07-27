"""Student Life & Organizations -- student government, registered student
organizations, and campus involvement, via Student Engagement and the
Illini Union."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    # No CrawlSeed for studentaffairs.illinois.edu: a real 200-question
    # sweep found a broad crawl of it had scattered 49 sub-pages (advisory
    # committees, advancement/giving, news archives, inclusive-excellence
    # committees -- an administrative parent-site hub, not practical
    # student-facing content) essentially randomly across topics with
    # nothing to do with their content, the same
    # doesn't-map-to-any-real-topic pollution pattern as
    # counselingcenter.illinois.edu (see recreation_wellness.py's SEEDS
    # comment for the fuller explanation). Deleted the 49 polluted
    # documents from the corpus alongside this change. The genuinely useful
    # student-org content lives at studentengagement.illinois.edu instead
    # (see SOURCES below), a different subdomain with a narrower, on-topic
    # scope.
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
