import httpx
import pytest

from app.ingestion.fetch import FetchError, build_client, fetch_url


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
