from datetime import UTC, datetime

import httpx
import pytest

from app.ingestion.fetch import FetchError, build_client, fetch_response, fetch_url


def _client_for(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler, follow_redirects=True)


async def test_build_client_sets_identifying_user_agent() -> None:
    async with build_client() as client:
        assert "IlliniGuideAI-Ingestion" in client.headers["user-agent"]


async def test_fetch_url_returns_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>ok</html>")

    async with _client_for(httpx.MockTransport(handler)) as client:
        body = await fetch_url("https://example.illinois.edu/page", client=client)

    assert body == b"<html>ok</html>"


async def test_fetch_url_raises_fetch_error_on_http_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchError):
            await fetch_url("https://example.illinois.edu/missing", client=client)


async def test_fetch_url_raises_fetch_error_on_transport_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    async with _client_for(httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchError):
            await fetch_url("https://example.illinois.edu/down", client=client)


async def test_fetch_url_follows_redirects() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new"})
        return httpx.Response(200, content=b"new content")

    async with _client_for(httpx.MockTransport(handler)) as client:
        body = await fetch_url("https://example.illinois.edu/old", client=client)

    assert body == b"new content"


async def test_fetch_response_sends_if_modified_since_header_when_given() -> None:
    captured: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("if-modified-since"))
        return httpx.Response(200, content=b"ok")

    async with _client_for(httpx.MockTransport(handler)) as client:
        await fetch_response(
            "https://example.illinois.edu/page",
            client=client,
            if_modified_since=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        )

    assert captured == ["Sun, 15 Mar 2026 10:00:00 GMT"]


async def test_fetch_response_omits_if_modified_since_header_when_not_given() -> None:
    captured: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("if-modified-since"))
        return httpx.Response(200, content=b"ok")

    async with _client_for(httpx.MockTransport(handler)) as client:
        await fetch_response("https://example.illinois.edu/page", client=client)

    assert captured == [None]


async def test_fetch_response_returns_304_without_raising() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(304)

    async with _client_for(httpx.MockTransport(handler)) as client:
        response = await fetch_response(
            "https://example.illinois.edu/page",
            client=client,
            if_modified_since=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        )

    assert response.status_code == 304
