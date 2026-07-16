"""Rule-based Audience inference: URL/department keyword signals, the
same style as crawler._infer_student_types -- falls back to the seed's
configured default, and ultimately to the two audiences nearly every
UIUC service page is relevant to, rather than an empty (unfiltered)
list."""

from app.models.document import Audience

_URL_KEYWORD_RULES: tuple[tuple[str, tuple[Audience, ...]], ...] = (
    ("newstudent.", (Audience.PROSPECTIVE_STUDENT,)),
    ("admissions.", (Audience.PROSPECTIVE_STUDENT,)),
    ("careercenter.", (Audience.CURRENT_STUDENT, Audience.ALUMNI)),
    ("hireillini.", (Audience.CURRENT_STUDENT, Audience.ALUMNI)),
)

_DEPARTMENT_KEYWORD_RULES: tuple[tuple[str, tuple[Audience, ...]], ...] = (
    ("admissions", (Audience.PROSPECTIVE_STUDENT,)),
    ("career", (Audience.CURRENT_STUDENT, Audience.ALUMNI)),
    ("technology services", (Audience.CURRENT_STUDENT, Audience.FACULTY_STAFF)),
    ("public safety", (Audience.CURRENT_STUDENT, Audience.FACULTY_STAFF, Audience.GENERAL_PUBLIC)),
)

# Nearly every UIUC service/program page is relevant both to someone
# already enrolled and to someone deciding whether to enroll -- a far
# better default than an empty, unfiltered audience list, matching the
# "best-guess beats blank" philosophy used for topic/student-type
# inference elsewhere in the crawler.
_DEFAULT: tuple[Audience, ...] = (Audience.CURRENT_STUDENT, Audience.PROSPECTIVE_STUDENT)


def infer_audience(
    url: str, department: str, default: tuple[Audience, ...] = ()
) -> tuple[Audience, ...]:
    lowered_url = url.lower()
    for marker, audiences in _URL_KEYWORD_RULES:
        if marker in lowered_url:
            return audiences

    lowered_department = department.lower()
    for keyword, audiences in _DEPARTMENT_KEYWORD_RULES:
        if keyword in lowered_department:
            return audiences

    return default or _DEFAULT
