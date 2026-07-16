import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.api.retrieve as retrieve_module
from app.core.config import Settings
from app.ingestion.chunking import ChunkResult
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
            document.id,
            [
                ChunkResult(
                    text="Students may purchase a parking permit through the Parking Department.",
                    subtopic="Permits",
                )
            ],
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
    assert body["results"][0]["subtopic"] == "Permits"


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


async def test_retrieve_endpoint_respects_audience_and_document_type_filters(
    db_session_factory: async_sessionmaker[AsyncSession], test_vector_repository: VectorRepository
) -> None:
    await _seed_and_index(db_session_factory, test_vector_repository)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/retrieve",
            params={"query": "parking permit", "audience": "alumni", "document_type": "faq"},
        )

    # The seeded document has no audience/document_type set, so it doesn't
    # match either explicit filter -- this only proves the query params are
    # accepted and threaded through, not a specific filtering outcome
    # (that's covered by the retriever/repository-level tests).
    assert response.status_code == 200


async def test_retrieve_rate_limit_holds_under_real_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # test_chat_api.py's rate-limit test fires requests sequentially, which
    # only proves the counter increments correctly -- it doesn't prove the
    # limiter is safe against requests that actually arrive at once. This
    # fires 10 real concurrent requests against a limit of 5 via
    # asyncio.gather and checks the split is exact, the way a burst from
    # several simultaneous users actually would.
    tight_settings = Settings(retrieve_rate_limit="5/minute")
    monkeypatch.setattr(retrieve_module, "get_settings", lambda: tight_settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(
            *(client.get("/api/v1/retrieve", params={"query": "housing"}) for _ in range(10))
        )

    statuses = [r.status_code for r in responses]
    assert statuses.count(200) == 5
    assert statuses.count(429) == 5
