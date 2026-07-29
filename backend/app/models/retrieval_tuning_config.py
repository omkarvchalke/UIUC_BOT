from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class RetrievalTuningConfig(Base):
    """Durable, tunable retrieval/reranking parameters -- e.g. `min_rerank_score`
    (app/graph/generation.py). Exists because Settings (app/core/config.py)
    is env-loaded once at process start and mutating it in place doesn't
    survive a restart; this table is the thing scripts/tune_retrieval_params.py
    writes to and app/api/dependencies.py::get_answer_generator reads from
    on every request on the no-Groq-key path.

    Keyed by string, not a single-row singleton: `rerank_top_k` and
    `topic_classification_confidence_threshold` are natural future additions
    as more rows, with zero schema change.
    """

    __tablename__ = "retrieval_tuning_config"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[float] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )
