import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.main import app
from app.models.feedback import Feedback


async def _create_session() -> str:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sessions", json={"student_type": "freshman"})
        return str(response.json()["id"])


async def test_submit_feedback_returns_201_and_stored_fields() -> None:
    session_id = await _create_session()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "session_id": session_id,
                "message_id": "msg-1",
                "question": "How do I apply as a freshman?",
                "answer": "Gather your materials, apply via Common App, pay the fee.",
                "rating": "helpful",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["session_id"] == session_id
    assert body["message_id"] == "msg-1"
    assert body["rating"] == "helpful"
    assert "id" in body
    assert "created_at" in body


async def test_submit_feedback_with_comment() -> None:
    session_id = await _create_session()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "session_id": session_id,
                "message_id": "msg-2",
                "question": "What are the library hours?",
                "answer": "The context does not specify the library hours.",
                "rating": "not_helpful",
                "comment": "This didn't answer my question at all.",
            },
        )

    assert response.status_code == 201
    assert response.json()["rating"] == "not_helpful"


async def test_submit_feedback_rejects_unknown_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "session_id": str(uuid.uuid4()),
                "message_id": "msg-3",
                "question": "test",
                "answer": "test",
                "rating": "helpful",
            },
        )

    assert response.status_code == 404


async def test_submit_feedback_stores_topic_and_citations(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    session_id = await _create_session()
    citation = {
        "title": "F-1 CPT",
        "url": "https://isss.illinois.edu/students/employment/f1-cpt/",
        "department": "International Student and Scholar Services",
        "topic": "international_students_immigration",
        "subtopic": None,
        "fused_score": 0.03,
        "rerank_score": 5.2,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "session_id": session_id,
                "message_id": "msg-5",
                "question": "How can I file for CPT?",
                "answer": "Submit the CPT application form to ISSS.",
                "rating": "helpful",
                "topic": "international_students_immigration",
                "citations": [citation],
            },
        )

    assert response.status_code == 201
    feedback_id = uuid.UUID(response.json()["id"])

    async with db_session_factory() as session:
        stored = await session.get(Feedback, feedback_id)
        assert stored is not None
        assert stored.topic == "international_students_immigration"
        assert stored.citations == [citation]


async def test_submit_feedback_without_topic_or_citations_still_succeeds(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # topic/citations must stay optional -- older frontend builds that
    # don't send them yet (or the pre-existing tests above, which also
    # never send them) must keep working.
    session_id = await _create_session()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "session_id": session_id,
                "message_id": "msg-6",
                "question": "test",
                "answer": "test",
                "rating": "helpful",
            },
        )

    assert response.status_code == 201
    feedback_id = uuid.UUID(response.json()["id"])

    async with db_session_factory() as session:
        stored = await session.get(Feedback, feedback_id)
        assert stored is not None
        assert stored.topic is None
        assert stored.citations is None


async def test_submit_feedback_rejects_invalid_rating() -> None:
    session_id = await _create_session()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={
                "session_id": session_id,
                "message_id": "msg-4",
                "question": "test",
                "answer": "test",
                "rating": "five_stars",
            },
        )

    assert response.status_code == 422


async def test_submit_feedback_rejects_missing_required_fields() -> None:
    session_id = await _create_session()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/feedback",
            json={"session_id": session_id, "rating": "helpful"},
        )

    assert response.status_code == 422
