import httpx

from app.ingestion.robots import RobotsChecker


async def test_allows_when_no_robots_txt_is_published() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    checker = RobotsChecker()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await checker.is_allowed("https://example.illinois.edu/apply", client) is True


async def test_respects_disallow_rule() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="User-agent: *\nDisallow: /private/\n")

    checker = RobotsChecker()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await checker.is_allowed("https://example.illinois.edu/private/page", client) is False
        )
        assert await checker.is_allowed("https://example.illinois.edu/public/page", client) is True


async def test_caches_one_fetch_per_domain() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(200, text="User-agent: *\nDisallow:\n")

    checker = RobotsChecker()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await checker.is_allowed("https://example.illinois.edu/a", client)
        await checker.is_allowed("https://example.illinois.edu/b", client)
        await checker.is_allowed("https://example.illinois.edu/c", client)

    assert request_count == 1


async def test_fails_open_on_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    checker = RobotsChecker()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert await checker.is_allowed("https://example.illinois.edu/page", client) is True
