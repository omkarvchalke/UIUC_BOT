from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_create_and_get_session() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_response = await client.post(
            "/api/v1/sessions",
            json={"student_type": "freshman", "semester": "Fall 2026"},
        )

        assert create_response.status_code == 201
        body = create_response.json()
        assert body["student_type"] == "freshman"
        assert body["semester"] == "Fall 2026"

        get_response = await client.get(f"/api/v1/sessions/{body['id']}")

        assert get_response.status_code == 200
        assert get_response.json()["id"] == body["id"]


async def test_create_session_without_profile_fields() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/sessions", json={})

        assert response.status_code == 201
        body = response.json()
        assert body["student_type"] is None
        assert body["semester"] is None


async def test_get_unknown_session_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/sessions/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404
