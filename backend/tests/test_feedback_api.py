import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app


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
