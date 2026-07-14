import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ingestion.sources import SourceConfig
from app.main import app
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.services.ingestion_service import IngestionService

_HTML = (
    "<html><head><title>Test Library Hours</title></head>"
    "<body><h1>Test Library Hours</h1>"
    "<p>The main library is open 24/7 during finals.</p></body></html>"
)


async def _seed_document(
    db_session_factory: async_sessionmaker[AsyncSession], *, url: str = "https://example.illinois.edu/library"
) -> str:
    async with db_session_factory() as session:
        service = IngestionService(DocumentRepository(session))
        source = SourceConfig(
            url=url,
            department="University Library",
            topic=Topic.LIBRARIES,
            source_type=SourceType.HTML,
            fallback_title="Fallback",
            student_types=(StudentType.FRESHMAN,),
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=_HTML.encode())

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            result = await service.ingest_source(source, http_client=client)

        document = await DocumentRepository(session).get_by_url(url)
        assert document is not None
        assert result.status == "created"
        return str(document.id)


async def test_list_documents_returns_seeded_document(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_document(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["documents"]) == 1
    assert body["documents"][0]["title"] == "Test Library Hours"
    assert body["documents"][0]["department"] == "University Library"


async def test_list_documents_respects_pagination() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/documents", params={"limit": 1, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 1
    assert body["offset"] == 0


async def test_list_documents_rejects_out_of_range_limit() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/documents", params={"limit": 1000})

    assert response.status_code == 422


async def test_get_document_returns_detail_with_chunks(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    document_id = await _seed_document(db_session_factory)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/documents/{document_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == document_id
    assert len(body["chunks"]) >= 1
    assert "24/7 during finals" in body["chunks"][0]["content"]


async def test_get_unknown_document_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/documents/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
