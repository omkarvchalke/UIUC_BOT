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
    # Topic.STUDENT_ORGANIZATIONS_ENGAGEMENT as a "least-wrong bucket" (see SOURCES
    # below) and was skewing that audit's reclassification toward
    # Topic.CAREER_EMPLOYMENT instead (nav-boilerplate-driven, not
    # content-driven -- Career Center pages share the same
    # jobs/Handshake-heavy site chrome). Deleted the product pages from the
    # corpus; kept the handful of genuinely informational pages (textbook
    # FAQ, buyback, options) as explicit sources instead.
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://commencement.illinois.edu/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR_GRADUATION,
        source_type=SourceType.HTML,
        fallback_title="Illinois Commencement",
    ),
    # Crawler-discovered but landed under ADMISSIONS (a live content-coverage audit found
    # "How do I order my cap and gown?" dead-ending despite this page existing with strong,
    # on-topic content) -- pinned here explicitly so it stays correctly tagged regardless of
    # what the crawler's classifier does with it on a future crawl.
    SourceConfig(
        url="https://commencement.illinois.edu/caps-and-gowns",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR_GRADUATION,
        source_type=SourceType.HTML,
        fallback_title="Caps and Gowns",
    ),
    # CAMPUS_SERVICES_FACILITIES, not FINANCIAL_AID_SCHOLARSHIPS: the previous taxonomy's
    # FINANCIAL_AID topic explicitly named "buying textbooks" in its description specifically to
    # fix a real regression ("Where do I buy textbooks?" was scoring below threshold without
    # it), and that reasoning was sound at the time -- textbooks genuinely are a cost-of-
    # attendance question. Source Manifest V2's own per-URL classification, however, places
    # these bookstore pages under Campus Services & Facilities (alongside the Illini Union
    # building and i-card services), not under either financial-aid topic -- followed here since
    # V2 is the authoritative source for this migration. "buying textbooks" moved to
    # CAMPUS_SERVICES_FACILITIES's description in topic_classifier.py to preserve the underlying
    # fix without contradicting V2's placement of the actual pages.
    SourceConfig(
        url="https://bookstore.illinois.edu/",
        department="Illini Union Bookstore",
        topic=Topic.CAMPUS_SERVICES_FACILITIES,
        source_type=SourceType.HTML,
        fallback_title="Illini Union Bookstore",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/site_textbookfaq.asp",
        department="Illini Union Bookstore",
        topic=Topic.CAMPUS_SERVICES_FACILITIES,
        source_type=SourceType.HTML,
        fallback_title="Textbook FAQ",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/site_buyback_info.asp",
        department="Illini Union Bookstore",
        topic=Topic.CAMPUS_SERVICES_FACILITIES,
        source_type=SourceType.HTML,
        fallback_title="Textbook Buyback",
    ),
    SourceConfig(
        url="https://bookstore.illinois.edu/site_text_options.asp",
        department="Illini Union Bookstore",
        topic=Topic.CAMPUS_SERVICES_FACILITIES,
        source_type=SourceType.HTML,
        fallback_title="Textbook Options",
    ),
)
