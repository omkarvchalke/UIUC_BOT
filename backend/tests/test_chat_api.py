import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.api.chat as chat_module
from app.core.config import Settings
from app.ingestion.chunking import ChunkResult
from app.main import app
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.vector_repository import VectorRepository
from app.services.indexing_service import IndexingService


async def _create_session(
    db_session_factory: async_sessionmaker[AsyncSession], *, student_type: StudentType | None
) -> uuid.UUID:
    async with db_session_factory() as session:
        conversation = await SessionRepository(session).create(
            student_type=student_type, semester=None, college=None, department=None
        )
        return conversation.id


async def _seed_and_index(
    db_session_factory: async_sessionmaker[AsyncSession],
    vector_repository: VectorRepository,
    *,
    url: str,
    title: str,
    chunk_texts: list[str],
    topic: Topic,
) -> None:
    async with db_session_factory() as session:
        repository = DocumentRepository(session)
        document = await repository.upsert_document(
            url=url,
            title=title,
            department="Test Department",
            topic=topic,
            source_type=SourceType.HTML,
            student_types=(),
            last_updated=None,
            content_hash=f"hash-{url}",
        )
        await repository.replace_chunks(document.id, [ChunkResult(text=t) for t in chunk_texts])
        loaded = await repository.get_by_id(document.id)
        assert loaded is not None
        await IndexingService(repository, vector_repository).index_document(loaded)


async def test_chat_greeting_returns_answer_without_citations(
    db_session_factory: async_sessionmaker[AsyncSession],
    override_checkpointer: None,
) -> None:
    session_id = await _create_session(db_session_factory, student_type=StudentType.FRESHMAN)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat", json={"session_id": str(session_id), "message": "hello"}
        )

    assert response.status_code == 200
    body = response.json()
    assert "IlliniAssist" in body["answer"]
    assert body["citations"] == []
    # Greeting turns skip question_classification entirely -- these should
    # genuinely be absent/null, not just unpopulated by coincidence.
    assert body["topic"] is None
    assert body["classification_confidence"] is None


async def test_chat_missing_profile_triggers_clarification(
    db_session_factory: async_sessionmaker[AsyncSession],
    override_checkpointer: None,
) -> None:
    session_id = await _create_session(db_session_factory, student_type=None)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"session_id": str(session_id), "message": "How do I apply for OPT?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["needs_clarification"] is True
    assert "freshman" in body["answer"].lower()


async def test_chat_full_question_returns_grounded_answer_with_citations(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    override_checkpointer: None,
) -> None:
    await _seed_and_index(
        db_session_factory,
        test_vector_repository,
        url="https://example.illinois.edu/parking",
        title="Parking Permits",
        chunk_texts=["Students may purchase a parking permit through the Parking Department."],
        topic=Topic.TRANSPORTATION,
    )
    session_id = await _create_session(db_session_factory, student_type=StudentType.FRESHMAN)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat",
            json={"session_id": str(session_id), "message": "How do I get a parking permit?"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert len(body["citations"]) >= 1
    assert body["citations"][0]["url"] == "https://example.illinois.edu/parking"
    assert isinstance(body["citations"][0]["fused_score"], float)
    assert "subtopic" in body["citations"][0]
    assert body["topic"] == "transportation"


async def test_chat_rejects_empty_message(override_checkpointer: None) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat", json={"session_id": str(uuid.uuid4()), "message": ""}
        )

    assert response.status_code == 422


async def test_chat_rejects_invalid_session_id(override_checkpointer: None) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/chat", json={"session_id": "not-a-uuid", "message": "hello"}
        )

    assert response.status_code == 422


async def test_chat_enforces_rate_limit(
    monkeypatch: pytest.MonkeyPatch, override_checkpointer: None
) -> None:
    # Chat calls a paid Groq API per request, so a client that loops or
    # retries aggressively should get throttled rather than run up cost --
    # this proves the limiter is actually wired up, not just configured.
    tight_settings = Settings(chat_rate_limit="2/minute")
    monkeypatch.setattr(chat_module, "get_settings", lambda: tight_settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"session_id": str(uuid.uuid4()), "message": "hello"}
        responses = [await client.post("/api/v1/chat", json=payload) for _ in range(3)]

    assert [r.status_code for r in responses] == [200, 200, 429]
