from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.retrieval_tuning_repository import RetrievalTuningRepository


async def test_get_returns_none_for_an_unseeded_key(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = RetrievalTuningRepository(session)
        assert await repository.get("min_rerank_score") is None


async def test_upsert_then_get_round_trips_the_value(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = RetrievalTuningRepository(session)
        await repository.upsert("min_rerank_score", 1.25)
        assert await repository.get("min_rerank_score") == 1.25


async def test_upsert_overwrites_an_existing_value(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = RetrievalTuningRepository(session)
        await repository.upsert("min_rerank_score", 1.0)
        await repository.upsert("min_rerank_score", 1.5)
        assert await repository.get("min_rerank_score") == 1.5


async def test_upsert_keys_are_independent(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        repository = RetrievalTuningRepository(session)
        await repository.upsert("min_rerank_score", 1.5)
        await repository.upsert("rerank_top_k", 8.0)
        assert await repository.get("min_rerank_score") == 1.5
        assert await repository.get("rerank_top_k") == 8.0
