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
    SourceConfig(
        url="https://parking.illinois.edu/permits",
        department="Parking Department",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Parking Permits",
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
        url="https://newstudent.illinois.edu/orientation/NSR",
        department="New Student & Family Experiences",
        topic=Topic.ORIENTATION,
        source_type=SourceType.HTML,
        fallback_title="New Student Registration",
        student_types=(StudentType.FRESHMAN, StudentType.TRANSFER),
    ),
    SourceConfig(
        url="https://isss.illinois.edu/",
        department="International Student and Scholar Services",
        topic=Topic.INTERNATIONAL_STUDENT_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="International Student and Scholar Services",
        student_types=(StudentType.INTERNATIONAL,),
    ),
    # The following 6 were checked individually via WebFetch against a
    # larger candidate list (~20 URLs from a hand-compiled domain list) --
    # most of that list turned out to be thin nav hubs, login-gated portals
    # (identity/canvas/app/handshake.illinois.edu), a JSON API response
    # (app.illinois.edu), or dead links; only these had real substantive
    # content worth adding.
    SourceConfig(
        url="https://housing.illinois.edu/Apply/New-Resident/How-To-Apply",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="New Resident: How to Apply",
    ),
    SourceConfig(
        url="https://housing.illinois.edu/MyHousing/Move-In",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="Fall Move-In",
    ),
    SourceConfig(
        url="https://www.osfa.illinois.edu/",
        department="Office of Student Financial Aid",
        topic=Topic.FINANCIAL_AID,
        source_type=SourceType.HTML,
        fallback_title="Office of Student Financial Aid",
    ),
    SourceConfig(
        url="https://counselingcenter.illinois.edu/",
        department="Counseling Center",
        # No dedicated "mental health" topic exists in this enum; HEALTH_INSURANCE
        # is the closest fit and already covers McKinley Health Center's
        # health-service content for the same reason.
        topic=Topic.HEALTH_INSURANCE,
        source_type=SourceType.HTML,
        fallback_title="Counseling Center",
    ),
    SourceConfig(
        url="https://fs.illinois.edu/campus-maps-and-building-information/",
        department="Facilities & Services",
        # Closest available fit: the page's real content is about GIS/digital
        # mapping infrastructure, not a topic this enum has a dedicated
        # bucket for.
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="Campus Maps and Building Information",
    ),
    SourceConfig(
        # Not an illinois.edu domain -- the official Champaign-Urbana Mass
        # Transit District site, which is the actual authority for bus fares
        # and routes serving campus (illinois.edu has no equivalent page of
        # its own). See the domain-safety test in test_sources.py for the
        # explicit allowlist this requires.
        url="https://mtd.org/",
        department="Champaign-Urbana Mass Transit District (MTD)",
        topic=Topic.TRANSPORTATION,
        source_type=SourceType.HTML,
        fallback_title="Champaign-Urbana Mass Transit District",
    ),
    # The following 20 were checked against a ~100-URL hand-compiled list
    # spanning many additional departments (banking, bursar, safety,
    # bookstore, etc.). Most of that list was either already covered, dead
    # links, login-gated, or thin nav hubs (see the same WebFetch-verify
    # pattern used for earlier additions) -- these had real substantive
    # content.
    SourceConfig(
        url="https://www.housing.illinois.edu/dine/purchase",
        department="University Housing",
        topic=Topic.DINING,
        source_type=SourceType.HTML,
        fallback_title="Purchasing Illini Cash and Meal Plans",
    ),
    SourceConfig(
        url="https://www.housing.illinois.edu/cost",
        department="University Housing",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        fallback_title="Costs",
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
    SourceConfig(
        url="https://grad.illinois.edu/",
        department="The Graduate College",
        topic=Topic.ADMISSIONS,
        source_type=SourceType.HTML,
        fallback_title="The Graduate College",
        student_types=(StudentType.GRADUATE,),
    ),
    SourceConfig(
        url="https://webstore.illinois.edu/home/",
        department="University of Illinois Webstore",
        topic=Topic.TECHNOLOGY_SERVICES,
        source_type=SourceType.HTML,
        fallback_title="University of Illinois Webstore",
    ),
    SourceConfig(
        url="https://catalog.illinois.edu/",
        department="Office of the Provost",
        topic=Topic.COURSE_REGISTRATION,
        source_type=SourceType.HTML,
        fallback_title="Course Catalog",
    ),
    SourceConfig(
        url="https://campusrec.illinois.edu/facilities",
        department="Campus Recreation",
        topic=Topic.CAMPUS_RECREATION,
        source_type=SourceType.HTML,
        fallback_title="Facilities",
    ),
    SourceConfig(
        url="https://hireillini.illinois.edu/",
        department="The Career Center",
        topic=Topic.STUDENT_EMPLOYMENT,
        source_type=SourceType.HTML,
        fallback_title="Hire Illini",
    ),
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
    SourceConfig(
        url="https://commencement.illinois.edu/",
        department="Office of the Registrar",
        topic=Topic.ACADEMIC_CALENDAR,
        source_type=SourceType.HTML,
        fallback_title="Illinois Commencement",
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
    SourceConfig(
        url="https://bookstore.illinois.edu/",
        department="Illini Union Bookstore",
        # No clean topical fit (retail, not a service category this enum
        # covers) -- STUDENT_ORGANIZATIONS is the least-wrong bucket among
        # "general campus life" topics.
        topic=Topic.STUDENT_ORGANIZATIONS,
        source_type=SourceType.HTML,
        fallback_title="Illini Union Bookstore",
    ),
    SourceConfig(
        # Topic.ACCESSIBILITY didn't exist until a crawl of dres.illinois.edu
        # (added to the approved-domains crawler) surfaced the gap: with no
        # accessibility-specific topic to embed against, the classifier was
        # tagging DRES pages as international_student_services, which is a
        # hard retrieval filter -- see app/retrieval/topic_classifier.py.
        # Both URLs verified substantive (real numbered steps, not nav-only)
        # via the crawler's own extraction during that smoke test.
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
