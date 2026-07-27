import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.embeddings.embedder import EMBEDDING_DIMENSION
from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import Audience, DocumentType, SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository


def _vector(seed: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[seed % EMBEDDING_DIMENSION] = 1.0
    return vector


async def _seed_chunk(
    repository: DocumentRepository,
    *,
    seed: int,
    topic: Topic = Topic.HOUSING,
    student_types: tuple[StudentType, ...] = (),
    audience: tuple[Audience, ...] = (),
    document_type: DocumentType | None = None,
) -> uuid.UUID:
    url = f"https://example.illinois.edu/{uuid.uuid4()}"
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
        content_hash=uuid.uuid4().hex,
    )
    await repository.replace_chunks(document.id, [ChunkResult(text=f"chunk {seed}")])
    loaded = await repository.get_by_id(document.id)
    assert loaded is not None
    await repository.set_chunk_embeddings(loaded.chunks, [_vector(seed)])
    return loaded.chunks[0].id


async def test_search_returns_matching_chunk(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        chunk_id = await _seed_chunk(repository, seed=1)

        results = await vectors.search(_vector(1), limit=5)

        assert any(r.id == str(chunk_id) for r in results)


async def test_search_filters_by_topic(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        housing_id = await _seed_chunk(repository, seed=1, topic=Topic.HOUSING)
        dining_id = await _seed_chunk(repository, seed=1, topic=Topic.DINING)

        results = await vectors.search(_vector(1), limit=10, topic=Topic.DINING)

        result_ids = {r.id for r in results}
        assert str(dining_id) in result_ids
        assert str(housing_id) not in result_ids


async def test_search_filters_by_student_type_including_documents_with_no_student_types(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        freshman_id = await _seed_chunk(repository, seed=1, student_types=(StudentType.FRESHMAN,))
        international_id = await _seed_chunk(
            repository, seed=1, student_types=(StudentType.INTERNATIONAL,)
        )
        everyone_id = await _seed_chunk(repository, seed=1, student_types=())

        results = await vectors.search(_vector(1), limit=10, student_type=StudentType.FRESHMAN)

        result_ids = {r.id for r in results}
        assert str(freshman_id) in result_ids
        assert str(everyone_id) in result_ids
        assert str(international_id) not in result_ids


async def test_search_filters_by_audience_including_documents_with_no_audience(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        alumni_id = await _seed_chunk(repository, seed=1, audience=(Audience.ALUMNI,))
        student_id = await _seed_chunk(repository, seed=1, audience=(Audience.CURRENT_STUDENT,))
        everyone_id = await _seed_chunk(repository, seed=1, audience=())

        results = await vectors.search(_vector(1), limit=10, audience=Audience.CURRENT_STUDENT)

        result_ids = {r.id for r in results}
        assert str(student_id) in result_ids
        assert str(everyone_id) in result_ids
        assert str(alumni_id) not in result_ids


async def test_search_filters_by_document_type(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        faq_id = await _seed_chunk(repository, seed=1, document_type=DocumentType.FAQ)
        policy_id = await _seed_chunk(repository, seed=1, document_type=DocumentType.POLICY)

        results = await vectors.search(_vector(1), limit=10, document_type=DocumentType.FAQ)

        result_ids = {r.id for r in results}
        assert str(faq_id) in result_ids
        assert str(policy_id) not in result_ids


async def test_search_filters_by_document_type_includes_documents_with_no_document_type_set(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        faq_id = await _seed_chunk(repository, seed=1, document_type=DocumentType.FAQ)
        unclassified_id = await _seed_chunk(repository, seed=1, document_type=None)

        results = await vectors.search(_vector(1), limit=10, document_type=DocumentType.FAQ)

        result_ids = {r.id for r in results}
        assert str(faq_id) in result_ids
        assert str(unclassified_id) in result_ids


async def test_search_excludes_chunks_with_no_embedding_yet(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        vectors = VectorRepository(session)
        document = await repository.upsert_document(
            url="https://example.illinois.edu/unindexed",
            title="Test Document",
            department="Test Department",
            topic=Topic.HOUSING,
            source_type=SourceType.HTML,
            student_types=(),
            last_updated=None,
            content_hash="hash-unindexed",
        )
        # Ingested (a real row exists) but never indexed -- embedding is
        # still null, exactly like a document between ingest and index.
        await repository.replace_chunks(document.id, [ChunkResult(text="never indexed")])

        results = await vectors.search(_vector(1), limit=10)

        assert results == []
