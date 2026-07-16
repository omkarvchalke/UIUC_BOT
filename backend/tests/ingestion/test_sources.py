from app.ingestion.sources import SOURCES
from app.models.conversation_session import StudentType
from app.models.document import Topic


def test_manifest_is_not_empty() -> None:
    assert len(SOURCES) > 0


# Non-illinois.edu domains explicitly vetted and allowed. Keep this list
# short and deliberate: the domain check below exists to catch an
# accidentally-added untrustworthy source, so an addition here should be a
# real, official authority for something illinois.edu itself doesn't
# publish -- not a convenience exception.
_ALLOWED_EXTERNAL_DOMAINS = (
    # Champaign-Urbana Mass Transit District: the actual authority for bus
    # fares/routes serving campus; illinois.edu has no equivalent page.
    "mtd.org",
)


def test_all_urls_are_https_and_on_the_illinois_edu_domain() -> None:
    for source in SOURCES:
        assert source.url.startswith("https://"), source.url
        # uillinois.edu (paymybill/studentmoney/treasury/icard...) is the
        # University of Illinois *System* domain covering all three
        # campuses, distinct from illinois.edu (Urbana-Champaign
        # specifically) but equally official -- ".illinois.edu" alone
        # doesn't match it (there's no dot before "illinois" in
        # "uillinois.edu"), so it needs its own check rather than silently
        # falling through to the external-domain allowlist.
        is_illinois_edu = ".illinois.edu" in source.url or ".uillinois.edu" in source.url
        is_allowed_external = any(domain in source.url for domain in _ALLOWED_EXTERNAL_DOMAINS)
        assert is_illinois_edu or is_allowed_external, source.url


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
