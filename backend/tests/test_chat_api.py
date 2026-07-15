import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
        await repository.replace_chunks(document.id, chunk_texts)
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
    assert "IlliniGuide" in body["answer"]
    assert body["citations"] == []


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
