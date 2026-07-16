"""Safety & Emergency -- campus policing, emergency preparedness, and
disability accommodations, via the Division of Public Safety, Emergency
Management, and Disability Resources and Educational Services (DRES)."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://police.illinois.edu",
        department="Division of Public Safety",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://ready.illinois.edu",
        department="Emergency Management",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://emergency.illinois.edu",
        department="Emergency Management",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://dres.illinois.edu",
        department="Disability Resources and Educational Services",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        # The root page's static text turned out thinner than it first
        # looked -- mostly nav links (SafeWalk, safety tips) plus rotating
        # news/crime-blotter snippets, no concrete phone numbers despite an
        # initial WebFetch summary suggesting otherwise (that summary
        # apparently drew on content this static scrape didn't actually
        # capture). The /contact/ subpage below has the real numbers;
        # keeping both since the root page's SafeWalk/mission content is
        # still real, just not the emergency-contact info a student most
        # likely wants.
        url="https://www.police.illinois.edu/",
        department="Division of Public Safety",
        topic=Topic.CAMPUS_SAFETY,
        source_type=SourceType.HTML,
        fallback_title="Division of Public Safety",
    ),
    SourceConfig(
        url="https://www.police.illinois.edu/contact/",
        department="Division of Public Safety",
        topic=Topic.CAMPUS_SAFETY,
        source_type=SourceType.HTML,
        fallback_title="Contact - Division of Public Safety",
    ),
    # Topic.ACCESSIBILITY didn't exist until a crawl of dres.illinois.edu
    # (added to the approved-domains crawler) surfaced the gap: with no
    # accessibility-specific topic to embed against, the classifier was
    # tagging DRES pages as international_student_services, which is a
    # hard retrieval filter -- see app/retrieval/topic_classifier.py.
    # Both URLs verified substantive (real numbered steps, not nav-only)
    # via the crawler's own extraction during that smoke test.
    SourceConfig(
        url="https://dres.illinois.edu/apply",
        department="Disability Resources and Educational Services",
        topic=Topic.ACCESSIBILITY,
        source_type=SourceType.HTML,
        fallback_title="Apply for Accommodations - DRES",
    ),
    SourceConfig(
        url="https://dres.illinois.edu/apply/documentation-requirements",
        department="Disability Resources and Educational Services",
        topic=Topic.ACCESSIBILITY,
        source_type=SourceType.HTML,
        fallback_title="Documentation Requirements - DRES",
    ),
)
