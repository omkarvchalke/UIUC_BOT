from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.api.dependencies import get_checkpointer, get_vector_repository
from app.core.config import get_settings
from app.database.session import get_db_session
from app.graph.checkpointer import build_checkpointer
from app.main import app
from app.repositories.vector_repository import VectorRepository

_TEST_QDRANT_COLLECTION = "illiniguide_documents_test"


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    # A dedicated test database (settings.test_database_url), never the real
    # dev database -- this table-cleanup fixture truncates aggressively, and
    # once truncated the real ingested UIUC corpus from scripts/run_ingestion.py.
    # NullPool: each checkout opens a fresh connection and closes it on checkin,
    # so nothing outlives the task/loop that created it. Avoids asyncpg
    # connections bleeding across the loop boundaries the test harness creates.
    engine = create_async_engine(get_settings().test_database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def override_db_session(test_engine: AsyncEngine) -> AsyncGenerator[None]:
    session_factory = async_sessionmaker(bind=test_engine, expire_on_commit=False)

    async def _get_db_session() -> AsyncGenerator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _get_db_session
    yield
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def db_session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # A factory, not an open session: each test opens/closes its own session
    # fully inside its own test-body task. A fixture that itself yields an
    # open session gets torn down by pytest-asyncio's finalizer on a separate
    # runner invocation, which was enough to occasionally desync asyncpg's
    # notion of "the current loop" even under the session-scoped event loop.
    return async_sessionmaker(bind=test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(test_engine: AsyncEngine) -> AsyncGenerator[None]:
    yield
    async with test_engine.begin() as conn:
        # feedback and chat_turn_events both FK to conversation_sessions --
        # truncating all three together in one statement satisfies
        # Postgres's FK check; truncating conversation_sessions alone would
        # fail once anything references it.
        await conn.execute(text("TRUNCATE TABLE feedback, chat_turn_events, conversation_sessions"))
        await conn.execute(text("TRUNCATE TABLE documents CASCADE"))


@pytest_asyncio.fixture
async def test_vector_repository() -> AsyncGenerator[VectorRepository]:
    # A dedicated collection, never the real configured one -- the dev
    # Qdrant instance already holds real indexed UIUC content from manual
    # runs of scripts/run_indexing.py, and tests must not read or clobber it.
    repository = VectorRepository(collection_name=_TEST_QDRANT_COLLECTION)
    await repository.ensure_collection()
    try:
        yield repository
    finally:
        await repository.delete_collection()


@pytest_asyncio.fixture(autouse=True)
async def override_vector_repository(
    test_vector_repository: VectorRepository,
) -> AsyncGenerator[None]:
    app.dependency_overrides[get_vector_repository] = lambda: test_vector_repository
    yield
    app.dependency_overrides.pop(get_vector_repository, None)


@pytest_asyncio.fixture
async def test_checkpointer() -> AsyncGenerator[AsyncPostgresSaver]:
    # Function-scoped, not session-scoped: AsyncPostgresSaver holds one
    # persistent psycopg connection (and an asyncio.Lock bound to whatever
    # loop was running when it opened) for its whole lifetime. Sharing that
    # across multiple test functions hit the same "bound to a different
    # event loop" failure class as the raw-session mistakes fixed earlier in
    # this test suite -- the fix here is the same: don't hold a live
    # connection open across a fixture boundary wider than one test.
    async with build_checkpointer(database_url=get_settings().test_database_url) as checkpointer:
        yield checkpointer


@pytest_asyncio.fixture
async def override_checkpointer(test_checkpointer: AsyncPostgresSaver) -> AsyncGenerator[None]:
    # Not autouse -- only tests that hit the chat API need this. The real
    # checkpointer lives on app.state, set up during the FastAPI lifespan,
    # which the AsyncClient(transport=ASGITransport(...)) pattern used
    # throughout these tests never triggers, so override the dependency
    # directly instead (same as get_vector_repository above). Every other
    # test would otherwise pay for a real Postgres connection it never uses.
    app.dependency_overrides[get_checkpointer] = lambda: test_checkpointer
    yield
    app.dependency_overrides.pop(get_checkpointer, None)
