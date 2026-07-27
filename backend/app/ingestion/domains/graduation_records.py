"""Graduation & Records -- commencement and the campus bookstore, via the
Office of the Registrar and the Illini Union Bookstore."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://commencement.illinois.edu",
        department="Office of the Registrar",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    # No CrawlSeed for bookstore.illinois.edu (only the explicit SOURCES
    # entries below): a 200-question-sweep follow-up audit (re-running the
    # topic classifier against every crawler-discovered document's stored
    # content) found 42 of its 57 crawled pages were individual e-commerce
    # product listings (t-shirts, hoodies, souvenirs -- confirmed live:
    # "ILLINOIS ARCH POWERBLEND HOOD", "ILLINOIS BLOCK I STADIUM S/S
    # T-SHIRT", ...), none of it informational content a campus assistant
    # should ever cite. It was previously all dumped into
    # Topic.STUDENT_ORGANIZATIONS as a "least-wrong bucket" (see SOURCES
    # below) and was skewing that audit's reclassification toward
    # Topic.STUDENT_EMPLOYMENT instead (nav-boilerplate-driven, not
    # content-driven -- Career Center pages share the same
    # jobs/Handshake-heavy site chrome). Deleted the product pages from the
    # corpus; kept the handful of genuinely informational pages (textbook
    # FAQ, buyback, options) as explicit sources instead.
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://commencement.illinois.edu/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR,
        source_type=SourceType.HTML,
        fallback_title="Illinois Commencement",
    ),
    # FINANCIAL_AID, not a "least-wrong bucket": textbooks are a real,
    # commonly-asked-about cost of attendance ("Where do I buy textbooks?"
    # was one of the 200 sweep questions), closer to "paying for college"
    # than any other topic here.
    SourceConfig(
        url="https://bookstore.illinois.edu/",
        department="Illini Union Bookstore",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Illini Union Bookstore",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/site_textbookfaq.asp",
        department="Illini Union Bookstore",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Textbook FAQ",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/site_buyback_info.asp",
        department="Illini Union Bookstore",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Textbook Buyback",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/site_text_options.asp",
        department="Illini Union Bookstore",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Textbook Options",
    ),
)
