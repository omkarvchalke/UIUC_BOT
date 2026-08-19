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
        topic=Topic.ACADEMIC_CALENDAR_GRADUATION,
        source_type=SourceType.HTML,
        fallback_title="Fall 2026 Academic Calendar",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/registration/",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION_RECORDS,
        source_type=SourceType.HTML,
        fallback_title="Registration",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/registration/how-to-register/",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION_RECORDS,
        source_type=SourceType.HTML,
        fallback_title="How to Register for Classes",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/graduation/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR_GRADUATION,
        source_type=SourceType.HTML,
        fallback_title="Graduation",
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/academic-records/transcripts/",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION_RECORDS,
        source_type=SourceType.HTML,
        fallback_title="Transcripts",
    ),
    # Explicit anchor for Topic.ACADEMICS (Source Manifest V2 migration): without at least one
    # manually-curated source, this topic exists only via crawler auto-classification, the same
    # gap international_services.py's own comment documents for VISA under the old taxonomy --
    # test_every_topic_has_at_least_one_source guards against exactly this.
    SourceConfig(
        url="https://courses.illinois.edu",
        department="Office of the Registrar",
        topic=Topic.ACADEMICS,
        source_type=SourceType.HTML,
        fallback_title="Course Explorer",
    ),
    # Closes a real content-coverage gap: a live audit found "How do I switch from letter grade
    # to pass/fail?" scoring below the rerank floor against every existing REGISTRATION_RECORDS
    # document -- none of them (registration/, how-to-register/, transcripts/) actually cover the
    # Credit/No Credit grading option, which is a distinct registrar process with its own page.
    SourceConfig(
        url="https://registrar.illinois.edu/registration/registration-process/credit-no-credit/",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION_RECORDS,
        source_type=SourceType.HTML,
        fallback_title="Credit/No Credit",
    ),
    # Closes a real content-coverage gap: a live audit found "What GPA counts toward academic
    # probation?" scoring below the rerank floor -- no existing source covers academic standing
    # rules at all. studentcode.illinois.edu, not registrar.illinois.edu, because Article 3 of the
    # Student Code is the actual campus-wide authority for this (individual colleges publish their
    # own probation pages with slightly different framing, but this is the single source that
    # applies university-wide rather than to one college).
    SourceConfig(
        url="https://studentcode.illinois.edu/article3/part1/3-110",
        department="Office of the Registrar",
        topic=Topic.REGISTRATION_RECORDS,
        source_type=SourceType.HTML,
        fallback_title="Academic Standing Rules (Student Code 3-110)",
    ),
)
