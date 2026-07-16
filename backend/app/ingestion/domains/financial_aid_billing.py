"""Financial Aid & Billing -- paying for UIUC: financial aid, scholarships,
tuition/bill payment, student banking, and the i-card, via OSFA, the
University Bursar, Student Money Management Center, Treasury, and the
I-Card Office."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://osfa.illinois.edu",
        department="Office of Student Financial Aid",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://paymybill.uillinois.edu",
        department="University Bursar",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://studentmoney.uillinois.edu",
        department="Student Money Management Center",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://treasury.uillinois.edu",
        department="University Treasury",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://icard.uillinois.edu",
        department="I-Card Office",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://www.osfa.illinois.edu/types-of-aid/",
        department="Office of Student Financial Aid",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Types of Aid",
    ),
    SourceConfig(
        url="https://www.osfa.illinois.edu/types-of-aid/scholarships/",
        department="Office of Student Financial Aid",
        topic=Topic.SCHOLARSHIPS,
        source_type=SourceType.HTML,
        fallback_title="Scholarships",
    ),
    SourceConfig(
        url="https://www.osfa.illinois.edu/types-of-aid/employment/",
        department="Office of Student Financial Aid",
        topic=Topic.STUDENT_EMPLOYMENT,
        source_type=SourceType.HTML,
        fallback_title="Student Employment",
    ),
    SourceConfig(
        url="https://www.osfa.illinois.edu/",
        department="Office of Student Financial Aid",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Office of Student Financial Aid",
    ),
    SourceConfig(
        url="https://www.studentmoney.uillinois.edu/",
        department="Student Money Management Center",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Student Money Management Center",
    ),
    SourceConfig(
        url="https://www.studentmoney.uillinois.edu/guides/InternationalStudents",
        department="Student Money Management Center",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Money Management for International Students",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://paymybill.uillinois.edu/",
        department="University Bursar",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Pay My Bill",
    ),
    SourceConfig(
        url="https://paymybill.uillinois.edu/refunds",
        department="University Bursar",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Refunds",
    ),
    SourceConfig(
        url="https://paymybill.uillinois.edu/refunds/freebankoptions",
        department="University Bursar",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Free Banking Options",
    ),
    SourceConfig(
        url="https://www.treasury.uillinois.edu/icp/banking",
        department="University Treasury",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Student Banking Program",
    ),
    SourceConfig(
        url="https://www.icard.uillinois.edu/public/bank-services.cfm",
        department="I-Card Office",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="i-card Banking Services",
    ),
    SourceConfig(
        url="https://icard.uillinois.edu/public/",
        department="I-Card Office",
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="i-card",
    ),
)
