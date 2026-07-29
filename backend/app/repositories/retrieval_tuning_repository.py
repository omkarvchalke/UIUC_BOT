from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval_tuning_config import RetrievalTuningConfig


class RetrievalTuningRepository:
    """Data access for RetrievalTuningConfig. No query logic belongs above
    this layer."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get(self, key: str) -> float | None:
        result = await self._db.execute(
            select(RetrievalTuningConfig.value).where(RetrievalTuningConfig.key == key)
        )
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: float) -> None:
        stmt = insert(RetrievalTuningConfig).values(key=key, value=value)
        stmt = stmt.on_conflict_do_update(
            index_elements=[RetrievalTuningConfig.key], set_={"value": value}
        )
        await self._db.execute(stmt)
        await self._db.commit()
