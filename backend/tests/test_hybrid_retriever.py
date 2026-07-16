from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import Audience, DocumentType, SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.hybrid_search import HybridRetriever
from app.services.indexing_service import IndexingService


async def _seed_and_index(
    session: AsyncSession,
    vector_repository: VectorRepository,
    *,
    url: str,
    chunk_texts: list[str],
    topic: Topic = Topic.HOUSING,
    student_types: tuple[StudentType, ...] = (),
    audience: tuple[Audience, ...] = (),
    document_type: DocumentType | None = None,
) -> None:
    repository = DocumentRepository(session)
    document = await repository.upsert_document(
        url=url,
        title="Test Document",
        department="Test Department",
        topic=topic,
        source_type=SourceType.HTML,
        student_types=student_types,
        audience=audience,
        document_type=document_type,
        last_updated=None,
        content_hash=f"hash-{url}",
    )
    await repository.replace_chunks(document.id, [ChunkResult(text=t) for t in chunk_texts])
    loaded_document = await repository.get_by_id(document.id)
    assert loaded_document is not None
    await IndexingService(repository, vector_repository).index_document(loaded_document)


async def test_search_finds_relevant_chunk_by_semantic_and_keyword_match(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/housing",
            chunk_texts=["Freshmen must live in undergraduate residence halls their first year."],
        )
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/library",
            chunk_texts=["The main library is open twenty-four hours during finals week."],
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search("Where do freshmen live on campus?", limit=5)

        assert len(results) >= 1
        assert "residence halls" in results[0].content


async def test_search_result_includes_citation_metadata(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/dining",
            chunk_texts=["Meal plans include Classic Meals and Dining Dollars."],
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search("meal plans", limit=5)

        assert len(results) >= 1
        top = results[0]
        assert top.url == "https://example.illinois.edu/dining"
        assert top.title == "Test Document"
        assert top.department == "Test Department"
        assert top.fused_score > 0
        assert top.semantic_rank is not None or top.bm25_rank is not None


async def test_search_respects_topic_filter(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/housing2",
            chunk_texts=["Campus housing options for new students."],
            topic=Topic.HOUSING,
        )
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/dining2",
            chunk_texts=["Campus dining options for new students."],
            topic=Topic.DINING,
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search(
            "campus options for new students", limit=10, topic=Topic.DINING
        )

        assert len(results) >= 1
        assert all(r.topic is Topic.DINING for r in results)


async def test_search_respects_student_type_filter_including_general_documents(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/international-only",
            chunk_texts=["CPT and OPT information for international students only."],
            student_types=(StudentType.INTERNATIONAL,),
        )
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/general",
            chunk_texts=["General campus information relevant to every student."],
            student_types=(),
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search(
            "campus information", limit=10, student_type=StudentType.FRESHMAN
        )

        urls = {r.url for r in results}
        assert "https://example.illinois.edu/general" in urls
        assert "https://example.illinois.edu/international-only" not in urls


async def test_search_returns_empty_list_for_empty_corpus(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search("anything at all", limit=5)
        assert results == []


async def test_search_respects_audience_filter_including_general_documents(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/alumni-only",
            chunk_texts=["Alumni association membership benefits and events."],
            audience=(Audience.ALUMNI,),
        )
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/general-audience",
            chunk_texts=["General campus services available to all audiences."],
            audience=(),
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search(
            "campus services", limit=10, audience=Audience.CURRENT_STUDENT
        )

        urls = {r.url for r in results}
        assert "https://example.illinois.edu/general-audience" in urls
        assert "https://example.illinois.edu/alumni-only" not in urls


async def test_search_respects_document_type_filter(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/faq-page",
            chunk_texts=["Frequently asked questions about campus parking."],
            document_type=DocumentType.FAQ,
        )
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/policy-page",
            chunk_texts=["Official policy document about campus parking rules."],
            document_type=DocumentType.POLICY,
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search("campus parking", limit=10, document_type=DocumentType.FAQ)

        urls = {r.url for r in results}
        assert "https://example.illinois.edu/faq-page" in urls
        assert "https://example.illinois.edu/policy-page" not in urls


async def test_search_combines_topic_student_type_and_audience_filters(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    # Regression test for the _build_filter restructuring: student_type and
    # audience are both "explicit match OR absent" (should-shaped) filters,
    # which incorrectly OR together if they aren't each nested as their own
    # Filter inside the outer must list (see VectorRepository._build_filter).
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/matches-all-filters",
            chunk_texts=["Freshman housing FAQ content matching every filter dimension."],
            topic=Topic.HOUSING,
            student_types=(StudentType.FRESHMAN,),
            audience=(Audience.CURRENT_STUDENT,),
        )
        # Wrong topic only.
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/wrong-topic",
            chunk_texts=["Freshman housing FAQ content but filed under dining."],
            topic=Topic.DINING,
            student_types=(StudentType.FRESHMAN,),
            audience=(Audience.CURRENT_STUDENT,),
        )
        # Wrong student_type only.
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/wrong-student-type",
            chunk_texts=["Freshman housing FAQ content but scoped to graduate students."],
            topic=Topic.HOUSING,
            student_types=(StudentType.GRADUATE,),
            audience=(Audience.CURRENT_STUDENT,),
        )
        # Wrong audience only.
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/wrong-audience",
            chunk_texts=["Freshman housing FAQ content but scoped to alumni."],
            topic=Topic.HOUSING,
            student_types=(StudentType.FRESHMAN,),
            audience=(Audience.ALUMNI,),
        )

        retriever = HybridRetriever(DocumentRepository(session), test_vector_repository)
        results = await retriever.search(
            "freshman housing FAQ content",
            limit=10,
            topic=Topic.HOUSING,
            student_type=StudentType.FRESHMAN,
            audience=Audience.CURRENT_STUDENT,
        )

        urls = {r.url for r in results}
        assert urls == {"https://example.illinois.edu/matches-all-filters"}
