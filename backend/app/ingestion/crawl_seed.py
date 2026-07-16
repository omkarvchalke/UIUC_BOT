from dataclasses import dataclass, field

from app.models.conversation_session import StudentType


@dataclass(frozen=True)
class CrawlSeed:
    """One starting point for the crawler: a site section to explore.

    Bounded deliberately -- path_prefixes keeps the crawl inside the
    relevant section of a site (e.g. admissions.illinois.edu/apply/*, not
    its news or staff-directory pages), and max_depth/max_pages cap how far
    a single seed can spread even if the section turns out to be larger
    than expected.

    Lives in its own module, not app.ingestion.crawler, specifically so
    app/ingestion/domains/*.py can import it without a circular import:
    crawler.py itself imports SOURCES/SourceConfig from sources.py, and
    sources.py (via app.ingestion.domains) needs every domain module's
    CrawlSeed entries -- if CrawlSeed lived in crawler.py, that would be
    crawler.py -> sources.py -> domains -> crawler.py.
    """

    start_url: str
    department: str
    path_prefixes: tuple[str, ...] = field(default_factory=tuple)
    default_student_types: tuple[StudentType, ...] = field(default_factory=tuple)
    max_depth: int = 2
    max_pages: int = 25
