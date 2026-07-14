import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware:
    """Pure ASGI middleware (not BaseHTTPMiddleware).

    BaseHTTPMiddleware runs the downstream app in a separate anyio task, which
    breaks greenlet-bound async DB drivers (asyncpg) with "attached to a
    different loop" errors. A pure ASGI middleware avoids that task boundary.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.info(
                "http_request",
                method=scope.get("method"),
                path=scope.get("path"),
                status_code=status_code,
                latency_ms=latency_ms,
            )
