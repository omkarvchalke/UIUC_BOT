from app.evaluation.golden_set import GOLDEN_SET
from app.models.conversation_session import StudentType


def test_case_names_are_unique() -> None:
    names = [case.name for case in GOLDEN_SET]
    assert len(names) == len(set(names))


def test_every_case_asserts_something() -> None:
    # A case that doesn't check grounded, clarification, citations, or
    # forbidden phrases can never fail -- it wouldn't be catching anything.
    for case in GOLDEN_SET:
        asserts_something = (
            case.expect_grounded is not None
            or case.expect_clarification is not None
            or case.min_citations > 0
            or len(case.forbidden_phrases) > 0
        )
        assert asserts_something, f"{case.name} has no assertions"


def test_forbidden_phrases_are_lowercase() -> None:
    # _check() lowercases the answer before matching; a mixed-case phrase
    # here would silently never match.
    for case in GOLDEN_SET:
        for phrase in case.forbidden_phrases:
            assert phrase == phrase.lower(), f"{case.name}: {phrase!r} is not lowercase"


def test_every_student_type_is_covered() -> None:
    covered = {case.student_type for case in GOLDEN_SET}
    missing = set(StudentType) - covered
    assert not missing, f"StudentTypes with no golden case: {missing}"
