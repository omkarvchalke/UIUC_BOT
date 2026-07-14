from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.document import SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.vector_repository import VectorRepository
from app.services.indexing_service import IndexingService


async def _seed_and_index(
    db_session_factory: async_sessionmaker[AsyncSession], vector_repository: VectorRepository
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.upsert_document(
            url="https://example.illinois.edu/parking",
            title="Parking and Transportation",
            department="Parking Department",
            topic=Topic.TRANSPORTATION,
            source_type=SourceType.HTML,
            student_types=(),
            last_updated=None,
            content_hash="hash-parking",
        )
        await repository.replace_chunks(
            document.id, ["Students may purchase a parking permit through the Parking Department."]
        )
        loaded_document = await repository.get_by_id(document.id)
        assert loaded_document is not None
        await IndexingService(repository, vector_repository).index_document(loaded_document)


async def test_retrieve_endpoint_returns_ranked_results(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    await _seed_and_index(db_session_factory, test_vector_repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/retrieve", params={"query": "parking permit"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "parking permit"
    assert len(body["results"]) >= 1
    assert "parking permit" in body["results"][0]["content"]
    assert body["results"][0]["fused_score"] > 0


async def test_retrieve_endpoint_requires_query_param() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/retrieve")

    assert response.status_code == 422


async def test_retrieve_endpoint_respects_topic_filter(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    await _seed_and_index(db_session_factory, test_vector_repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/retrieve", params={"query": "parking permit", "topic": "dining"}
        )

    assert response.status_code == 200
    assert response.json()["results"] == []
