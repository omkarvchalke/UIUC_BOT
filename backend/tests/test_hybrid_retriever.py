from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic
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
) -> None:
    repository = DocumentRepository(session)
    document = await repository.upsert_document(
        url=url,
        title="Test Document",
        department="Test Department",
        topic=topic,
        source_type=SourceType.HTML,
        student_types=student_types,
        last_updated=None,
        content_hash=f"hash-{url}",
    )
    await repository.replace_chunks(document.id, chunk_texts)
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
