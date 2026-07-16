from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.embeddings.embedder import Embedder
from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import Document, SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository
from app.services.indexing_service import IndexingService


async def _seed_document(
    session: AsyncSession, *, url: str, chunk_texts: list[str]
) -> Document | None:
    repository = DocumentRepository(session)
    document = await repository.upsert_document(
        url=url,
        title="Test Document",
        department="Test Department",
        topic=Topic.HOUSING,
        source_type=SourceType.HTML,
        student_types=(StudentType.FRESHMAN,),
        last_updated=None,
        content_hash="hash-v1",
    )
    await repository.replace_chunks(document.id, [ChunkResult(text=t) for t in chunk_texts])
    return await repository.get_by_id(document.id)


async def test_index_document_creates_points_in_qdrant(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        document = await _seed_document(
            session,
            url="https://example.illinois.edu/a",
            chunk_texts=["First chunk about housing."],
        )
        assert document is not None

        service = IndexingService(DocumentRepository(session), test_vector_repository)
        result = await service.index_document(document)

        assert result.status == "indexed"
        assert result.chunk_count == 1

        query_vector = Embedder().embed_query("housing")
        found = await test_vector_repository.search(query_vector, limit=1)
        assert len(found) == 1
        assert found[0].payload is not None
        assert found[0].payload["content"] == "First chunk about housing."


async def test_index_document_skips_when_hash_unchanged(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        document = await _seed_document(
            session, url="https://example.illinois.edu/b", chunk_texts=["Some content."]
        )
        assert document is not None
        repository = DocumentRepository(session)
        service = IndexingService(repository, test_vector_repository)

        first = await service.index_document(document)
        reloaded = await repository.get_by_id(document.id)
        assert reloaded is not None
        second = await service.index_document(reloaded)

        assert first.status == "indexed"
        assert second.status == "skipped"


async def test_index_document_with_no_chunks_fails_gracefully(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.upsert_document(
            url="https://example.illinois.edu/empty",
            title="Empty Document",
            department="Test Department",
            topic=Topic.HOUSING,
            source_type=SourceType.HTML,
            student_types=(),
            last_updated=None,
            content_hash="hash-empty",
        )
        loaded_document = await repository.get_by_id(document.id)
        assert loaded_document is not None

        service = IndexingService(repository, test_vector_repository)
        result = await service.index_document(loaded_document)

        assert result.status == "failed"
        assert result.error is not None


async def test_index_all_only_processes_documents_needing_index(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        await _seed_document(
            session, url="https://example.illinois.edu/c", chunk_texts=["Chunk one."]
        )
        repository = DocumentRepository(session)
        service = IndexingService(repository, test_vector_repository)

        first_run = await service.index_all()
        second_run = await service.index_all()

        assert len(first_run) == 1
        assert first_run[0].status == "indexed"
        assert len(second_run) == 0
