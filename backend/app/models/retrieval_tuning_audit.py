import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, Float, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class RetrievalTuningAudit(Base):
    """One row per retrieval-tuning run that actually evaluated a candidate
    value (scripts/tune_retrieval_params.py) -- whether the candidate was
    applied or rejected by the golden-set non-regression gate
    (app/evaluation/tuning_gate.py). This table is the whole safety net for
    "automatic" tuning with no per-change human approval: it's how a human
    notices and reverts a bad change after the fact (see the script's
    --revert flag). Runs that stopped earlier for insufficient feedback
    volume don't get a row here -- there's no decision to reconstruct for
    those, only a structlog line.
    """

    __tablename__ = "retrieval_tuning_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    parameter: Mapped[str] = mapped_column(Text)
    old_value: Mapped[float] = mapped_column(Float)
    # Equal to old_value when applied=False (the candidate was rejected).
    new_value: Mapped[float] = mapped_column(Float)
    applied: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)
    sample_size: Mapped[int] = mapped_column(Integer)
    flag_rate: Mapped[float] = mapped_column(Float)
    golden_set_before: Mapped[dict[str, Any]] = mapped_column(JSONB)
    golden_set_after: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
