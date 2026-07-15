from app.ingestion.sources import SOURCES
from app.models.conversation_session import StudentType
from app.models.document import Topic


def test_manifest_is_not_empty() -> None:
    assert len(SOURCES) > 0


def test_all_urls_are_https_and_on_the_illinois_edu_domain() -> None:
    for source in SOURCES:
        assert source.url.startswith("https://"), source.url
        assert ".illinois.edu" in source.url, source.url


def test_all_urls_are_unique() -> None:
    urls = [source.url for source in SOURCES]
    assert len(urls) == len(set(urls))


def test_every_source_has_department_and_fallback_title() -> None:
    for source in SOURCES:
        assert source.department.strip()
        assert source.fallback_title.strip()


def test_pdf_sources_point_at_pdf_urls() -> None:
    from app.models.document import SourceType

    for source in SOURCES:
        if source.source_type is SourceType.PDF:
            assert source.url.lower().endswith(".pdf"), source.url


def test_every_topic_has_at_least_one_source() -> None:
    # Guards against a topic silently having zero sources -- retrieval for
    # that topic would then always come back empty regardless of how good
    # the retriever is, and nothing about the retrieval code itself would
    # ever flag it.
    covered_topics = {source.topic for source in SOURCES}
    missing = set(Topic) - covered_topics
    assert not missing, f"Topics with no source at all: {missing}"


def test_every_student_type_has_admissions_coverage() -> None:
    # student_type is a hard retrieval filter (app/repositories/
    # vector_repository.py): a document scoped to one StudentType never
    # surfaces for a query from a different one, and only a document with
    # student_types=() (applies to everyone) is exempt. Admissions sources
    # scoped only to FRESHMAN silently returned zero results for
    # transfer/graduate/international admissions questions -- confirmed
    # live via /api/v1/retrieve before these sources were added. This test
    # would have caught that gap without needing a live server.
    admissions_sources = [s for s in SOURCES if s.topic is Topic.ADMISSIONS]
    for student_type in StudentType:
        applies = [
            s
            for s in admissions_sources
            if not s.student_types or student_type in s.student_types
        ]
        assert applies, f"No admissions source applies to {student_type}"
