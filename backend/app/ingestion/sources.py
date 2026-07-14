from dataclasses import dataclass, field

from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic


@dataclass(frozen=True)
class SourceConfig:
    """One entry in the ingestion manifest: an official UIUC URL plus the
    metadata that isn't reliably extractable from the page itself.

    New sources are added by appending to `SOURCES` below -- this is the
    single place the ingestion pipeline reads its worklist from.
    """

    url: str
    department: str
    topic: Topic
    source_type: SourceType
    fallback_title: str
    student_types: tuple[StudentType, ...] = field(default_factory=tuple)


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
    SourceConfig(
        url="https://housing.illinois.edu/living-communities/halls/undergraduate",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="Undergraduate Halls",
        student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    SourceConfig(
        url="https://housing.illinois.edu/dine/meal-plans/meal-plans",
        department="University Housing",
        topic=Topic.DINING,
        source_type=SourceType.HTML,
        fallback_title="Meal Plans",
    ),
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
    SourceConfig(
        url="https://isss.illinois.edu/students/incoming/orientation/ug_orientation.html",
        department="International Student and Scholar Services",
        topic=Topic.ORIENTATION,
        source_type=SourceType.HTML,
        fallback_title="Fall Semester International Undergraduate Student Orientation",
        student_types=(StudentType.INTERNATIONAL, StudentType.FRESHMAN),
    ),
    SourceConfig(
        url="https://newstudent.illinois.edu/orientation",
        department="New Student & Family Experiences",
        topic=Topic.ORIENTATION,
        source_type=SourceType.HTML,
        fallback_title="Orientation",
        student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    SourceConfig(
        url="https://registrar.illinois.edu/fall-2026-academic-calendar/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR,
        source_type=SourceType.HTML,
        fallback_title="Fall 2026 Academic Calendar",
    ),
    SourceConfig(
        url="https://www.library.illinois.edu/library-hours/",
        department="University Library",
        topic=Topic.LIBRARIES,
        source_type=SourceType.HTML,
        fallback_title="Library Hours",
    ),
    SourceConfig(
        url="https://www.techservices.illinois.edu/",
        department="Technology Services",
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="Technology Services",
    ),
    SourceConfig(
        url="https://campusrec.illinois.edu/membership",
        department="Campus Recreation",
        topic=Topic.CAMPUS_RECREATION,
        source_type=SourceType.HTML,
        fallback_title="Membership",
    ),
    SourceConfig(
        url="https://mckinley.illinois.edu/fees/health-service-fee",
        department="McKinley Health Center",
        topic=Topic.HEALTH_INSURANCE,
        source_type=SourceType.HTML,
        fallback_title="Health Service Fee",
    ),
    SourceConfig(
        url="https://studentengagement.illinois.edu/soda/studentorgs/registration",
        department="Student Engagement",
        topic=Topic.STUDENT_ORGANIZATIONS,
        source_type=SourceType.HTML,
        fallback_title="Student Org Registration",
    ),
    SourceConfig(
        url="https://parking.illinois.edu/transportation",
        department="Parking Department",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Transportation",
    ),
)
