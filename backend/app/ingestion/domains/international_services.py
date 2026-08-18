"""International Student Services -- visas, OPT/CPT work authorization, and
orientation for international students, via International Student and
Scholar Services (ISSS)."""

from app.core.config import get_settings
from app.ingestion.crawl_seed import CrawlSeed
from app.ingestion.source_config import SourceConfig
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic

_DEFAULT_MAX_DEPTH = get_settings().crawl_default_max_depth
_DEFAULT_MAX_PAGES = get_settings().crawl_default_max_pages

SEEDS: tuple[CrawlSeed, ...] = (
    CrawlSeed(
        start_url="https://isss.illinois.edu",
        department="International Student and Scholar Services",
        default_student_types=(StudentType.INTERNATIONAL,),
        max_depth=_DEFAULT_MAX_DEPTH,
        max_pages=_DEFAULT_MAX_PAGES,
    ),
)

SOURCES: tuple[SourceConfig, ...] = (
    SourceConfig(
        url="https://isss.illinois.edu/students/employment/f1-opt/",
        department="International Student and Scholar Services",
        topic=Topic.OPT,
        source_type=SourceType.HTML,
        fallback_title="F-1 Optional Practical Training (OPT)",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/students/employment/f1-cpt/",
        department="International Student and Scholar Services",
        topic=Topic.CPT,
        source_type=SourceType.HTML,
        fallback_title="F-1 Curricular Practical Training (CPT)",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/wp-content/uploads/2025/08/SAMPLE-I-20.pdf",
        department="International Student and Scholar Services",
        topic=Topic.VISA,
        source_type=SourceType.PDF,
        fallback_title="Sample Form I-20",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    # The four sources below were added after a corpus audit found Topic.
    # VISA had only 2 real documents (23 chunks, vs. 300+ for several other
    # topics) -- the broad isss.illinois.edu crawl above just doesn't
    # auto-classify many pages as primarily "visa status" specifically
    # (most ISSS content is about OPT/CPT or general services instead).
    # Verified live (HTTP 200, substantive real content, not JS-shell/thin)
    # before adding, same as every other manual SOURCES entry here.
    SourceConfig(
        url="https://isss.illinois.edu/students/f1j1-nonimmstatus/",
        department="International Student and Scholar Services",
        topic=Topic.VISA,
        source_type=SourceType.HTML,
        fallback_title="Maintaining F-1/J-1 Status",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/students/f1j1-travel/",
        department="International Student and Scholar Services",
        topic=Topic.VISA,
        source_type=SourceType.HTML,
        fallback_title="F-1/J-1 Travel",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/students/incoming/pre_arrival/immigration.html",
        department="International Student and Scholar Services",
        topic=Topic.VISA,
        source_type=SourceType.HTML,
        fallback_title="Pre-Arrival Information",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/students/returning-students/",
        department="International Student and Scholar Services",
        topic=Topic.VISA,
        source_type=SourceType.HTML,
        fallback_title="Returning Students",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/students/incoming/orientation/ug_orientation.html",
        department="International Student and Scholar Services",
        topic=Topic.ORIENTATION,
        source_type=SourceType.HTML,
        fallback_title="Fall Semester International Undergraduate Student Orientation",
        student_types=(StudentType.INTERNATIONAL, StudentType.FRESHMAN),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/",
        department="International Student and Scholar Services",
        topic=Topic.INTERNATIONAL_STUDENT_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="International Student and Scholar Services",
        student_types=(StudentType.INTERNATIONAL,),
    ),
)
