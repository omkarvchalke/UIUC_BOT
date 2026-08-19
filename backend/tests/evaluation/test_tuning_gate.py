from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.evaluation.golden_set import EvalCase
from app.evaluation.tuning_gate import run_tuning_gate
from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.services.indexing_service import IndexingService

# Deliberately not GOLDEN_SET: those 20 cases assume the real, ingested
# UIUC corpus, which the test DB never has. A small, self-seeded case set
# lets this test control exactly what "grounded"/"citation-sufficient"/
# "ground-truth-matching" mean for the assertions below.
_LOW_CONFIDENCE_THRESHOLD = 0.0


async def _seed(
    db_session_factory: async_sessionmaker[AsyncSession],
    *,
    url: str,
    title: str,
    chunk_texts: list[str],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.upsert_document(
            url=url,
            title=title,
            department="Test Department",
            topic=Topic.INTERNATIONAL_STUDENTS_IMMIGRATION,
            source_type=SourceType.HTML,
            student_types=(),
            last_updated=None,
            content_hash=f"hash-{url}",
        )
        await repository.replace_chunks(document.id, [ChunkResult(text=t) for t in chunk_texts])
        loaded = await repository.get_by_id(document.id)
        assert loaded is not None
        await IndexingService(repository).index_document(loaded)


async def test_reports_grounded_and_citation_rates_over_the_given_cases(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        db_session_factory,
        url="https://isss.illinois.edu/cpt",
        title="CPT",
        chunk_texts=["Curricular Practical Training (CPT) authorizes off-campus employment."],
    )
    cases = (
        EvalCase(
            name="cpt_question",
            message="What is CPT?",
            student_type=StudentType.INTERNATIONAL,
            min_citations=1,
        ),
    )

    async with db_session_factory() as session:
        result = await run_tuning_gate(
            1.0,
            session,
            topic_classification_confidence_threshold=_LOW_CONFIDENCE_THRESHOLD,
            cases=cases,
        )

    assert result.case_count == 1
    assert result.grounded_rate == 1.0
    assert result.citation_sufficiency_rate == 1.0


async def test_a_higher_min_rerank_score_can_drop_below_min_citations(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Two chunks, both genuinely about CPT (so a lenient floor scores and
    # picks a sentence from each -- 2 citations), min_citations=2. An
    # impossibly high floor filters every chunk out of consideration, which
    # falls back to dumping the single top chunk verbatim (see
    # ExtractiveAnswerGenerator.generate's "no picks" branch) -- only 1
    # citation, below min_citations=2. This is the proof this gate is
    # actually sensitive to min_rerank_score, unlike the HTTP-based
    # runners this module's docstring explains it deliberately doesn't
    # reuse -- a single-chunk case can't show this, since that fallback
    # always cites exactly 1 chunk regardless of score.
    await _seed(
        db_session_factory,
        url="https://isss.illinois.edu/cpt-eligibility",
        title="CPT Eligibility",
        chunk_texts=["F-1 students become eligible for CPT after one full academic year."],
    )
    await _seed(
        db_session_factory,
        url="https://isss.illinois.edu/cpt-application",
        title="CPT Application",
        chunk_texts=["Students apply for CPT by submitting the CPT request form to ISSS."],
    )
    cases = (
        EvalCase(
            name="cpt_question",
            message="What is CPT?",
            student_type=StudentType.INTERNATIONAL,
            min_citations=2,
        ),
    )

    async with db_session_factory() as session:
        lenient = await run_tuning_gate(
            0.0,
            session,
            topic_classification_confidence_threshold=_LOW_CONFIDENCE_THRESHOLD,
            cases=cases,
        )
        strict = await run_tuning_gate(
            1000.0,
            session,
            topic_classification_confidence_threshold=_LOW_CONFIDENCE_THRESHOLD,
            cases=cases,
        )

    assert lenient.citation_sufficiency_rate == 1.0
    assert strict.citation_sufficiency_rate == 0.0


async def test_context_precision_is_none_when_no_case_has_ground_truth_urls(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        db_session_factory,
        url="https://isss.illinois.edu/cpt",
        title="CPT",
        chunk_texts=["Curricular Practical Training (CPT) authorizes off-campus employment."],
    )
    cases = (
        EvalCase(
            name="cpt_question",
            message="What is CPT?",
            student_type=StudentType.INTERNATIONAL,
            min_citations=1,
        ),
    )

    async with db_session_factory() as session:
        result = await run_tuning_gate(
            1.0,
            session,
            topic_classification_confidence_threshold=_LOW_CONFIDENCE_THRESHOLD,
            cases=cases,
        )

    assert result.context_precision is None


async def test_context_precision_reflects_expected_relevant_urls(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed(
        db_session_factory,
        url="https://isss.illinois.edu/cpt",
        title="CPT",
        chunk_texts=["Curricular Practical Training (CPT) authorizes off-campus employment."],
    )
    cases = (
        EvalCase(
            name="cpt_question",
            message="What is CPT?",
            student_type=StudentType.INTERNATIONAL,
            min_citations=1,
            expected_relevant_urls=("https://isss.illinois.edu/cpt",),
        ),
    )

    async with db_session_factory() as session:
        result = await run_tuning_gate(
            1.0,
            session,
            topic_classification_confidence_threshold=_LOW_CONFIDENCE_THRESHOLD,
            cases=cases,
        )

    assert result.context_precision == 1.0
