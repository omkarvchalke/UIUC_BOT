"""
API-level tests: health check, response schemas for /api/chat,
/api/chat/stream, and /api/retrieve, and basic /api/sources coverage.

These intentionally check *shape* (status codes, field names, field types,
allowed enum values), never exact LLM wording — answer content depends on
a real OPENAI_API_KEY and isn't something a schema test should pin down.
Where an endpoint requires a real key that may not be configured, the test
accepts either a valid success schema or the documented 503 config-error
response, so this suite is meaningful with or without a key present.

Run with:
    cd backend && source .venv/bin/activate
    pytest ../tests/test_api.py -v
"""
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy", "service": "campusguide-ai-backend"}


def test_chat_schema_for_blocked_private_data_question():
    """Private-data questions are blocked before any embedding/LLM call
    (see app/core/safety.py), so this schema check is meaningful even with
    no OPENAI_API_KEY configured at all."""
    resp = client.post("/api/chat", json={"question": "What is my UIN?"})
    assert resp.status_code == 200

    body = resp.json()
    assert set(body.keys()) == {
        "answer",
        "sources",
        "confidence",
        "next_steps",
        "requires_official_confirmation",
    }
    assert isinstance(body["answer"], str) and body["answer"]
    assert body["sources"] == []
    assert body["confidence"] in ("high", "medium", "low")
    assert isinstance(body["next_steps"], list)
    assert all(isinstance(step, str) for step in body["next_steps"])
    assert isinstance(body["requires_official_confirmation"], bool)
    assert body["requires_official_confirmation"] is True
    assert "private student systems" in body["answer"]


def test_chat_rejects_empty_question():
    resp = client.post("/api/chat", json={"question": ""})
    assert resp.status_code == 422


def test_chat_rejects_missing_question_field():
    resp = client.post("/api/chat", json={})
    assert resp.status_code == 422


def test_chat_accepts_history_field_on_blocked_path():
    """History is parsed and validated even on the safety-blocked path
    (which never reaches the LLM), so this is meaningful without a real
    LLM key configured."""
    resp = client.post(
        "/api/chat",
        json={
            "question": "What is my UIN?",
            "history": [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello! How can I help?"},
            ],
        },
    )
    assert resp.status_code == 200


def test_chat_rejects_too_many_history_turns():
    resp = client.post(
        "/api/chat",
        json={
            "question": "Hi",
            "history": [{"role": "user", "content": "x"}] * 21,
        },
    )
    assert resp.status_code == 422


def test_chat_rejects_invalid_history_role():
    resp = client.post(
        "/api/chat",
        json={
            "question": "Hi",
            "history": [{"role": "system", "content": "x"}],
        },
    )
    assert resp.status_code == 422


def _parse_sse_events(raw: str) -> list[dict]:
    events = []
    for frame in raw.split("\n\n"):
        for line in frame.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: ") :]))
    return events


def test_chat_stream_schema_for_blocked_private_data_question():
    """Same private-data short-circuit as the /api/chat test above, but
    over the SSE endpoint — no LLM call is made, so this is meaningful
    without a real LLM key configured."""
    resp = client.post("/api/chat/stream", json={"question": "What is my UIN?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_events(resp.text)
    assert len(events) == 2

    delta, done = events
    assert delta["type"] == "delta"
    assert "private student systems" in delta["text"]

    assert done["type"] == "done"
    assert set(done.keys()) == {
        "type",
        "sources",
        "confidence",
        "next_steps",
        "requires_official_confirmation",
    }
    assert done["sources"] == []
    assert done["confidence"] == "low"
    assert done["requires_official_confirmation"] is True


def test_chat_stream_rejects_empty_question():
    resp = client.post("/api/chat/stream", json={"question": ""})
    assert resp.status_code == 422


def test_chat_stream_rejects_too_many_history_turns():
    resp = client.post(
        "/api/chat/stream",
        json={"question": "Hi", "history": [{"role": "user", "content": "x"}] * 21},
    )
    assert resp.status_code == 422


def test_retrieve_schema_or_graceful_config_error():
    """Embeddings run locally (no API key needed), so this normally succeeds
    with a 200 regardless of LLM provider configuration. Still accepts a
    503 config-error response too, in case EMBEDDING_PROVIDER is ever
    misconfigured to something not yet implemented — both are correct
    behavior for their respective states, so neither should fail this test."""
    resp = client.post("/api/retrieve", json={"question": "When is Welcome Week?"})

    if resp.status_code == 503:
        assert "EMBEDDING_PROVIDER" in resp.json()["detail"] or "embed" in resp.json()["detail"].lower()
        return

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"results"}
    for result in body["results"]:
        assert set(result.keys()) == {
            "chunk_text",
            "source_title",
            "source_url",
            "category",
            "department",
            "score",
        }
        assert isinstance(result["score"], (int, float))


def test_retrieve_rejects_empty_question():
    resp = client.post("/api/retrieve", json={"question": ""})
    assert resp.status_code == 422


def test_sources_endpoint_schema():
    resp = client.get("/api/sources")
    assert resp.status_code == 200

    body = resp.json()
    assert "sources" in body
    assert len(body["sources"]) > 0
    for source in body["sources"]:
        assert set(source.keys()) == {
            "title",
            "category",
            "department",
            "url",
            "source_type",
        }
        assert source["url"].startswith("https://")


def test_sources_endpoint_category_filter():
    resp = client.get("/api/sources", params={"category": "icard"})
    assert resp.status_code == 200

    body = resp.json()
    assert len(body["sources"]) >= 1
    assert all(s["category"] == "icard" for s in body["sources"])
