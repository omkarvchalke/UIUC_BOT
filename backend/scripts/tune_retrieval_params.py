"""Automatic retrieval-parameter tuning: uses accumulated thumbs-up/down
feedback (app/models/feedback.py) to decide whether ExtractiveAnswerGenerator's
min_rerank_score floor (app/graph/generation.py) should be raised, and -- if
enough evidence exists -- validates the candidate against the golden set
(app/evaluation/golden_set.py, gated via app/evaluation/tuning_gate.py)
before persisting it (app/models/retrieval_tuning_config.py).

This is "automatic" in the sense that no human approves each individual
change, but every change is bounded and audited (app/models/retrieval_tuning_audit.py):
a minimum feedback sample size, a small step size, a hard ceiling, and a
mandatory non-regression check against the golden set. See
app/services/retrieval_tuning_service.py's module docstring for the exact
decision logic.

No scheduler exists in this backend (by design -- see the plan this
implements), so this is a manually- or externally-triggered script, exactly
like scripts/eval_rag.py and scripts/backfill_semantic_chunks.py, not a
daemon. Run it by hand, or wire up a cron entry / scheduled CI workflow
that invokes it periodically -- that wiring is outside this script's scope.

Usage (from backend/):
    uv run python -m scripts.tune_retrieval_params
    uv run python -m scripts.tune_retrieval_params --dry-run
    uv run python -m scripts.tune_retrieval_params --revert <audit_row_id>

Exit code: 0 on any outcome that isn't a genuine failure (including
"insufficient samples" and "golden set regression, not applied") -- so a
cron/CI wrapper only alerts on real breakage (DB unreachable, an
unexpected exception), not routine no-ops.
"""

import argparse
import asyncio
import uuid
from dataclasses import asdict

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.evaluation.tuning_gate import TuningGateResult, run_tuning_gate
from app.graph.generation import _MIN_RERANK_SCORE_DEFAULT
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.retrieval_tuning_audit_repository import RetrievalTuningAuditRepository
from app.repositories.retrieval_tuning_repository import RetrievalTuningRepository
from app.services.retrieval_tuning_service import (
    DEFAULT_MIN_SAMPLES,
    DEFAULT_STEP_SIZE,
    compute_candidate,
)

configure_logging()
logger = get_logger(__name__)

_PARAMETER = "min_rerank_score"
# A safe float slack, not zero: context_precision is an average over
# ground-truth-bearing cases, and re-running the same graph twice can move
# it by float noise alone (e.g. embedding non-determinism doesn't apply
# here, but ties in reranking order can). A genuine regression is much
# larger than this.
_CONTEXT_PRECISION_SLACK = 0.01


def _detect_regression(before: TuningGateResult, after: TuningGateResult) -> bool:
    if after.grounded_rate < before.grounded_rate:
        return True
    if after.citation_sufficiency_rate < before.citation_sufficiency_rate:
        return True
    if before.context_precision is not None and after.context_precision is not None:
        if after.context_precision < before.context_precision - _CONTEXT_PRECISION_SLACK:
            return True
    return False


async def _revert(audit_id: uuid.UUID) -> int:
    session_factory = get_session_factory()
    async with session_factory() as db:
        tuning_repo = RetrievalTuningRepository(db)
        audit_repo = RetrievalTuningAuditRepository(db)

        audit = await audit_repo.get_by_id(audit_id)
        if audit is None:
            logger.error("tuning_revert_not_found", audit_id=str(audit_id))
            return 1
        if not audit.applied:
            logger.error("tuning_revert_target_not_applied", audit_id=str(audit_id))
            return 1

        await tuning_repo.upsert(_PARAMETER, audit.old_value)
        # A revert is itself part of the permanent trail, not an
        # out-of-band action -- golden_set_before/after are swapped from
        # the row being reverted (this direction was already measured
        # then) rather than re-running the gate for a simple rollback.
        await audit_repo.create(
            parameter=_PARAMETER,
            old_value=audit.new_value,
            new_value=audit.old_value,
            applied=True,
            reason="manual_revert",
            sample_size=audit.sample_size,
            flag_rate=audit.flag_rate,
            golden_set_before=audit.golden_set_after,
            golden_set_after=audit.golden_set_before,
        )
        logger.info(
            "tuning_reverted",
            audit_id=str(audit_id),
            restored_value=audit.old_value,
        )
        return 0


async def _tune(*, dry_run: bool, min_samples: int, step_size: float) -> int:
    session_factory = get_session_factory()
    async with session_factory() as db:
        tuning_repo = RetrievalTuningRepository(db)
        audit_repo = RetrievalTuningAuditRepository(db)
        feedback_repo = FeedbackRepository(db)

        current_value = await tuning_repo.get(_PARAMETER)
        if current_value is None:
            current_value = _MIN_RERANK_SCORE_DEFAULT

        last_applied_at = await audit_repo.last_applied_at(_PARAMETER)
        feedback_rows = await feedback_repo.list_since(last_applied_at)

        candidate = compute_candidate(
            current_value,
            feedback_rows,
            min_samples=min_samples,
            step_size=step_size,
        )

        if candidate.reason != "candidate":
            logger.info(
                "tuning_skipped",
                reason=candidate.reason,
                sample_size=candidate.sample_size,
                flag_rate=candidate.flag_rate,
                current_value=current_value,
            )
            return 0

        assert candidate.candidate_value is not None  # narrows for mypy; reason == "candidate"
        settings = get_settings()
        gate_kwargs = {
            "topic_classification_confidence_threshold": (
                settings.topic_classification_confidence_threshold
            ),
        }
        before = await run_tuning_gate(current_value, db, **gate_kwargs)
        after = await run_tuning_gate(candidate.candidate_value, db, **gate_kwargs)
        regressed = _detect_regression(before, after)
        applied = not regressed and not dry_run
        reason = "golden_set_regression" if regressed else "applied"

        logger.info(
            "tuning_candidate_evaluated",
            current_value=current_value,
            candidate_value=candidate.candidate_value,
            sample_size=candidate.sample_size,
            flag_rate=candidate.flag_rate,
            golden_set_before=asdict(before),
            golden_set_after=asdict(after),
            regressed=regressed,
            dry_run=dry_run,
            applied=applied,
        )

        if dry_run:
            return 0

        if applied:
            await tuning_repo.upsert(_PARAMETER, candidate.candidate_value)

        await audit_repo.create(
            parameter=_PARAMETER,
            old_value=current_value,
            new_value=candidate.candidate_value if applied else current_value,
            applied=applied,
            reason=reason,
            sample_size=candidate.sample_size,
            flag_rate=candidate.flag_rate or 0.0,
            golden_set_before=asdict(before),
            golden_set_after=asdict(after),
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute the candidate and run the golden-set gate, but never write anything.",
    )
    parser.add_argument(
        "--revert",
        metavar="AUDIT_ROW_ID",
        help="Restore the old_value from the given retrieval_tuning_audit_log row.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=None,
        help="Override the minimum feedback sample size (see retrieval_tuning_service.py).",
    )
    parser.add_argument(
        "--step-size",
        type=float,
        default=None,
        help="Override the per-run step size (default: see retrieval_tuning_service.py).",
    )
    args = parser.parse_args()

    if args.revert:
        return asyncio.run(_revert(uuid.UUID(args.revert)))

    min_samples = args.min_samples if args.min_samples is not None else DEFAULT_MIN_SAMPLES
    step_size = args.step_size if args.step_size is not None else DEFAULT_STEP_SIZE
    return asyncio.run(_tune(dry_run=args.dry_run, min_samples=min_samples, step_size=step_size))


if __name__ == "__main__":
    raise SystemExit(main())
