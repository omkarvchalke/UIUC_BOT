from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.feedback import router as feedback_router
from app.api.health import router as health_router
from app.api.retrieve import router as retrieve_router
from app.api.sessions import router as sessions_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestLoggingMiddleware
from app.core.rate_limit import limiter
from app.graph.checkpointer import build_checkpointer

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info("app_startup", app_name=settings.app_name, environment=settings.environment)
    # Opened once for the app's lifetime, not per-request: AsyncPostgresSaver
    # holds one persistent connection, and the conversation graph is
    # rebuilt cheaply per-request around this shared checkpointer.
    async with build_checkpointer() as checkpointer:
        app.state.checkpointer = checkpointer
        yield
    logger.info("app_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered onboarding assistant for UIUC students.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter

    def _handle_rate_limit(request: Request, exc: Exception) -> Response:
        # slowapi's own handler is typed for RateLimitExceeded specifically;
        # Starlette's registry requires the wider Exception signature, and
        # this handler is only ever invoked for RateLimitExceeded (that's
        # what it's registered against below).
        assert isinstance(exc, RateLimitExceeded)
        return _rate_limit_exceeded_handler(request, exc)

    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(sessions_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(retrieve_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
    app.include_router(feedback_router, prefix="/api/v1")

    return app


app = create_app()
