from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.database.session import get_db_session
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine]:
    # NullPool: each checkout opens a fresh connection and closes it on checkin,
    # so nothing outlives the task/loop that created it. Avoids asyncpg
    # connections bleeding across the loop boundaries the test harness creates.
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)
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
        await conn.execute(text("TRUNCATE TABLE conversation_sessions"))
        await conn.execute(text("TRUNCATE TABLE documents CASCADE"))
