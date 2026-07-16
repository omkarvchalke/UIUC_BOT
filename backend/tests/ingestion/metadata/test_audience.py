from app.ingestion.metadata.audience import infer_audience
from app.models.document import Audience


def test_admissions_url_marker() -> None:
    result = infer_audience("https://admissions.illinois.edu/apply", "Undergraduate Admissions")
    assert result == (Audience.PROSPECTIVE_STUDENT,)


def test_career_url_marker_includes_alumni() -> None:
    result = infer_audience("https://careercenter.illinois.edu/jobs", "The Career Center")
    assert Audience.ALUMNI in result
    assert Audience.CURRENT_STUDENT in result


def test_department_keyword_when_no_url_marker() -> None:
    result = infer_audience("https://example.illinois.edu/apply", "Undergraduate Admissions")
    assert result == (Audience.PROSPECTIVE_STUDENT,)


def test_falls_back_to_seed_default_when_no_rule_matches() -> None:
    result = infer_audience(
        "https://housing.illinois.edu/faq",
        "University Housing",
        default=(Audience.CURRENT_STUDENT,),
    )
    assert result == (Audience.CURRENT_STUDENT,)


def test_falls_back_to_current_and_prospective_when_nothing_matches_at_all() -> None:
    result = infer_audience("https://housing.illinois.edu/faq", "University Housing")
    assert result == (Audience.CURRENT_STUDENT, Audience.PROSPECTIVE_STUDENT)


def test_url_marker_takes_priority_over_seed_default() -> None:
    result = infer_audience(
        "https://admissions.illinois.edu/apply",
        "Undergraduate Admissions",
        default=(Audience.FACULTY_STAFF,),
    )
    assert result == (Audience.PROSPECTIVE_STUDENT,)
