"""Admissions & Enrollment -- becoming a new UIUC student: freshman,
transfer, graduate, and international undergraduate/graduate admissions,
plus new-student orientation and registration."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://admissions.illinois.edu",
        department="Undergraduate Admissions",
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://grad.illinois.edu",
        department="The Graduate College",
        default_student_types=(StudentType.GRADUATE,),
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
    CrawlSeed(
        start_url="https://newstudent.illinois.edu",
        department="New Student & Family Experiences",
        default_student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/freshman",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="First-Year Applicants",
        student_types=(StudentType.FRESHMAN,),
    ),
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/freshman/dates",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="First-Year Application Dates",
        student_types=(StudentType.FRESHMAN,),
    ),
    # The two sources above are both "gateway" pages -- mostly nav links,
    # with the actual step-by-step process and requirements living on
    # separate subpages. Retrieval was pulling nav-menu text as the top
    # chunks for "how do I apply" questions, producing answers that only
    # gestured at "follow the process on the website" instead of real
    # steps. Confirmed via GET /api/v1/retrieve before adding these.
    SourceConfig(
        url="https://www.admissions.illinois.edu/Apply/Freshman/process",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="How to Apply: First-Year Process",
        student_types=(StudentType.FRESHMAN,),
    ),
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/freshman/requirements",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="First-Year Admission Requirements",
        student_types=(StudentType.FRESHMAN,),
    ),
    SourceConfig(
        url="https://newstudent.illinois.edu/orientation",
        department="New Student & Family Experiences",
        topic=Topic.ORIENTATION,
        source_type=SourceType.HTML,
        fallback_title="Orientation",
        student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    # The two freshman admissions sources above only apply to
    # StudentType.FRESHMAN -- since student_type is a hard retrieval filter
    # (a document with no student_types applies to everyone, but one scoped
    # to FRESHMAN only will never surface for a transfer/graduate/
    # international query), transfer and graduate students asking an
    # admissions question got zero admissions results. These sources close
    # that gap. (Found via a live /api/v1/retrieve check with
    # student_type=transfer returning no admissions-topic hits at all.)
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/transfer/dates",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="Transfer Admission Dates & Deadlines",
        student_types=(StudentType.TRANSFER,),
    ),
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/transfer/gpa-guidelines",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="Transfer GPA Guidelines",
        student_types=(StudentType.TRANSFER,),
    ),
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/transfer/process",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="How to Apply: Transfer Process",
        student_types=(StudentType.TRANSFER,),
    ),
    SourceConfig(
        url="https://www.admissions.illinois.edu/apply/international",
        department="Undergraduate Admissions",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="International Undergraduate Admissions",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://grad.illinois.edu/admissions/graduate-admissions-minimum-requirements",
        department="The Graduate College",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="Graduate Admissions Minimum Requirements",
        student_types=(StudentType.GRADUATE,),
    ),
    SourceConfig(
        url="https://grad.illinois.edu/admissions/application-faq/requirements-deadlines",
        department="The Graduate College",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="Graduate Admission Requirements & Deadlines FAQ",
        student_types=(StudentType.GRADUATE,),
    ),
    SourceConfig(
        url="https://grad.illinois.edu/admissions/application-instructions/completing-your-graduate-application",
        department="The Graduate College",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="Completing Your Graduate Application",
        student_types=(StudentType.GRADUATE,),
    ),
    SourceConfig(
        url="https://newstudent.illinois.edu/orientation/NSR",
        department="New Student & Family Experiences",
        topic=Topic.ORIENTATION,
        source_type=SourceType.HTML,
        fallback_title="New Student Registration",
        student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    SourceConfig(
        url="https://grad.illinois.edu/",
        department="The Graduate College",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="The Graduate College",
        student_types=(StudentType.GRADUATE,),
    ),
)
