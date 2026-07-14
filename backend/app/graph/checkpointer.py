from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings


def to_psycopg_dsn(sqlalchemy_url: str) -> str:
    """SQLAlchemy's async driver DSN (postgresql+asyncpg://...) isn't a
    scheme psycopg understands -- it wants plain postgresql://."""
    return sqlalchemy_url.replace("postgresql+asyncpg://", "postgresql://", 1)


@asynccontextmanager
async def build_checkpointer(
    *, database_url: str | None = None
) -> AsyncIterator[AsyncPostgresSaver]:
    """Persistent, Postgres-backed conversation memory for the graph.

    Not an in-memory MemorySaver: this is what makes "Save Conversation
    State" durable across process restarts and multiple backend instances,
    reusing the Postgres we already run rather than adding new
    infrastructure. Tables are created idempotently via `.setup()` on first
    use.
    """
    dsn = to_psycopg_dsn(database_url or get_settings().database_url)
    async with AsyncPostgresSaver.from_conn_string(dsn) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
