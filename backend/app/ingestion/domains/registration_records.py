"""Registration & Academic Records -- registering for classes, the
academic calendar, transcripts, and graduation/degree records, via the
Office of the Registrar."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://registrar.illinois.edu",
        department="Office of the Registrar",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://courses.illinois.edu",
        department="Office of the Registrar",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://registrar.illinois.edu/fall-2026-academic-calendar/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR,
        source_type=SourceType.HTML,
        fallback_title="Fall 2026 Academic Calendar",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/registration/",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION,
        source_type=SourceType.HTML,
        fallback_title="Registration",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/registration/how-to-register/",
        department="Office of the Registrar",
        topic=Topic.COURSE_REGISTRATION,
        source_type=SourceType.HTML,
        fallback_title="How to Register for Classes",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/graduation/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR,
        source_type=SourceType.HTML,
        fallback_title="Graduation",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/academic-records/transcripts/",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION,
        source_type=SourceType.HTML,
        fallback_title="Transcripts",
    ),
)
