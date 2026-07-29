import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.retrieval_tuning_audit import RetrievalTuningAudit


class RetrievalTuningAuditRepository:
    """Data access for RetrievalTuningAudit. No query logic belongs above
    this layer."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        parameter: str,
        old_value: float,
        new_value: float,
        applied: bool,
        reason: str,
        sample_size: int,
        flag_rate: float,
        golden_set_before: dict[str, Any],
        golden_set_after: dict[str, Any],
    ) -> RetrievalTuningAudit:
        audit = RetrievalTuningAudit(
            parameter=parameter,
            old_value=old_value,
            new_value=new_value,
            applied=applied,
            reason=reason,
            sample_size=sample_size,
            flag_rate=flag_rate,
            golden_set_before=golden_set_before,
            golden_set_after=golden_set_after,
        )
        self._db.add(audit)
        await self._db.commit()
        await self._db.refresh(audit)
        return audit

    async def last_applied_at(self, parameter: str) -> datetime | None:
        # Used to scope scripts/tune_retrieval_params.py's next run to only
        # feedback newer than the last change that was actually applied --
        # rejected-candidate runs don't move this cursor forward, since
        # nothing about the underlying parameter changed.
        query = (
            select(RetrievalTuningAudit.created_at)
            .where(
                RetrievalTuningAudit.parameter == parameter,
                RetrievalTuningAudit.applied.is_(True),
            )
            .order_by(RetrievalTuningAudit.created_at.desc())
            .limit(1)
        )
        result = await self._db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, audit_id: uuid.UUID) -> RetrievalTuningAudit | None:
        return await self._db.get(RetrievalTuningAudit, audit_id)
