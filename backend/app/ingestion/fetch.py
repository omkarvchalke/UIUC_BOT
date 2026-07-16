import httpx

_USER_AGENT = "IlliniGuideAI-Ingestion/0.1 (educational RAG project; respects robots.txt)"
_DEFAULT_TIMEOUT = 15.0


class FetchError(Exception):
    pass


def build_client(timeout: float = _DEFAULT_TIMEOUT) -> httpx.AsyncClient:
    """A client configured for ingestion, reusable across many `fetch_url` calls."""
    return httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
    )


async def fetch_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> bytes:
    """Fetch raw bytes for a source URL.

    Accepts an optional pre-built client so callers can reuse a connection
    pool across many sources, and so tests can inject an httpx.MockTransport
    instead of hitting the network.
    """
    response = await fetch_response(url, client=client, timeout=timeout)
    return response.content


async def fetch_response(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> httpx.Response:
    """Like fetch_url, but returns the full Response -- for callers that
    need the post-redirect URL or Content-Type header (the crawler, to
    detect a login-wall redirect or a non-HTML response), not just the
    body bytes.
    """
    owns_client = client is None
    http_client = client or build_client(timeout)
    try:
        response = await http_client.get(url)
        response.raise_for_status()
        return response
    except httpx.HTTPError as exc:
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc
    finally:
        if owns_client:
            await http_client.aclose()
