import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import scripts.tune_retrieval_params as tune_script
from app.evaluation.tuning_gate import TuningGateResult
from app.models.feedback import FeedbackRating
from app.models.retrieval_tuning_audit import RetrievalTuningAudit
from app.repositories.feedback_repository import FeedbackRepository
from app.repositories.retrieval_tuning_audit_repository import RetrievalTuningAuditRepository
from app.repositories.retrieval_tuning_repository import RetrievalTuningRepository
from app.repositories.session_repository import SessionRepository

_NO_REGRESSION_GATE_RESULT = TuningGateResult(
    grounded_rate=1.0, citation_sufficiency_rate=1.0, context_precision=None, case_count=20
)
_REGRESSED_GATE_RESULT = TuningGateResult(
    grounded_rate=0.5, citation_sufficiency_rate=1.0, context_precision=None, case_count=20
)


async def _no_regression_gate(*_args: object, **_kwargs: object) -> TuningGateResult:
    return _NO_REGRESSION_GATE_RESULT


@pytest.fixture(autouse=True)
def _use_test_db(
    monkeypatch: pytest.MonkeyPatch, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # scripts/tune_retrieval_params.py talks to the real deployed DB via
    # get_session_factory() -- not the FastAPI dependency-override
    # mechanism conftest.py's other fixtures use -- so redirect it at the
    # test database directly for this file only.
    monkeypatch.setattr(tune_script, "get_session_factory", lambda: db_session_factory)


async def _seed_feedback(
    db_session_factory: async_sessionmaker[AsyncSession],
    *,
    count: int,
    rating: FeedbackRating,
    rerank_score: float,
) -> None:
    async with db_session_factory() as session:
        session_id = (
            await SessionRepository(session).create(
                student_type=None, semester=None, college=None, department=None
            )
        ).id
        repository = FeedbackRepository(session)
        for i in range(count):
            await repository.create(
                session_id=session_id,
                message_id=f"msg-{uuid.uuid4()}-{i}",
                question="What is CPT?",
                answer="Some answer.",
                rating=rating,
                comment=None,
                citations=[{"url": "https://example.illinois.edu", "rerank_score": rerank_score}],
            )


async def test_insufficient_feedback_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_feedback(
        db_session_factory, count=5, rating=FeedbackRating.NOT_HELPFUL, rerank_score=0.1
    )
    monkeypatch.setattr(tune_script, "run_tuning_gate", _no_regression_gate)

    exit_code = await tune_script._tune(dry_run=False, min_samples=20, step_size=0.25)

    assert exit_code == 0
    async with db_session_factory() as session:
        assert (await RetrievalTuningRepository(session).get("min_rerank_score")) is None
        audit_rows = (await session.execute(select(RetrievalTuningAudit))).scalars().all()
        assert audit_rows == []


async def test_enough_signal_and_no_regression_applies_and_audits(
    monkeypatch: pytest.MonkeyPatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_feedback(
        db_session_factory, count=20, rating=FeedbackRating.NOT_HELPFUL, rerank_score=0.1
    )

    async def _fake_gate(min_rerank_score: float, *_args: object, **_kwargs: object):
        return _NO_REGRESSION_GATE_RESULT

    monkeypatch.setattr(tune_script, "run_tuning_gate", _fake_gate)

    exit_code = await tune_script._tune(dry_run=False, min_samples=20, step_size=0.25)

    assert exit_code == 0
    async with db_session_factory() as session:
        assert (await RetrievalTuningRepository(session).get("min_rerank_score")) == pytest.approx(
            1.25
        )
        audit_rows = (await session.execute(select(RetrievalTuningAudit))).scalars().all()
        assert len(audit_rows) == 1
        audit = audit_rows[0]
        assert audit.applied is True
        assert audit.reason == "applied"
        assert audit.old_value == pytest.approx(1.0)
        assert audit.new_value == pytest.approx(1.25)
        assert audit.sample_size == 20


async def test_regression_detected_does_not_apply_but_still_audits(
    monkeypatch: pytest.MonkeyPatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_feedback(
        db_session_factory, count=20, rating=FeedbackRating.NOT_HELPFUL, rerank_score=0.1
    )

    async def _fake_gate(min_rerank_score: float, *_args: object, **_kwargs: object):
        # The "after" (candidate) call gets the regressed result; "before"
        # (current_value) gets the clean one -- distinguish by value since
        # both calls otherwise look identical to this fake.
        return _REGRESSED_GATE_RESULT if min_rerank_score > 1.0 else _NO_REGRESSION_GATE_RESULT

    monkeypatch.setattr(tune_script, "run_tuning_gate", _fake_gate)

    exit_code = await tune_script._tune(dry_run=False, min_samples=20, step_size=0.25)

    assert exit_code == 0
    async with db_session_factory() as session:
        # Rejected candidate must never be persisted.
        assert (await RetrievalTuningRepository(session).get("min_rerank_score")) is None
        audit_rows = (await session.execute(select(RetrievalTuningAudit))).scalars().all()
        assert len(audit_rows) == 1
        audit = audit_rows[0]
        assert audit.applied is False
        assert audit.reason == "golden_set_regression"
        assert audit.new_value == pytest.approx(audit.old_value)


async def test_dry_run_evaluates_but_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_feedback(
        db_session_factory, count=20, rating=FeedbackRating.NOT_HELPFUL, rerank_score=0.1
    )
    monkeypatch.setattr(tune_script, "run_tuning_gate", _no_regression_gate)

    exit_code = await tune_script._tune(dry_run=True, min_samples=20, step_size=0.25)

    assert exit_code == 0
    async with db_session_factory() as session:
        assert (await RetrievalTuningRepository(session).get("min_rerank_score")) is None
        audit_rows = (await session.execute(select(RetrievalTuningAudit))).scalars().all()
        assert audit_rows == []


async def test_revert_restores_old_value_and_audits_the_revert(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with db_session_factory() as session:
        tuning_repo = RetrievalTuningRepository(session)
        audit_repo = RetrievalTuningAuditRepository(session)
        await tuning_repo.upsert("min_rerank_score", 1.25)
        applied_audit = await audit_repo.create(
            parameter="min_rerank_score",
            old_value=1.0,
            new_value=1.25,
            applied=True,
            reason="applied",
            sample_size=20,
            flag_rate=0.2,
            golden_set_before={"grounded_rate": 1.0},
            golden_set_after={"grounded_rate": 1.0},
        )
        audit_id = applied_audit.id

    exit_code = await tune_script._revert(audit_id)

    assert exit_code == 0
    async with db_session_factory() as session:
        assert (await RetrievalTuningRepository(session).get("min_rerank_score")) == pytest.approx(
            1.0
        )
        audit_rows = (
            (
                await session.execute(
                    select(RetrievalTuningAudit).order_by(RetrievalTuningAudit.created_at)
                )
            )
            .scalars()
            .all()
        )
        assert len(audit_rows) == 2
        revert_audit = audit_rows[1]
        assert revert_audit.reason == "manual_revert"
        assert revert_audit.applied is True
        assert revert_audit.old_value == pytest.approx(1.25)
        assert revert_audit.new_value == pytest.approx(1.0)


async def test_revert_unknown_audit_id_fails_without_writing(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    exit_code = await tune_script._revert(uuid.uuid4())

    assert exit_code == 1
    async with db_session_factory() as session:
        assert (await RetrievalTuningRepository(session).get("min_rerank_score")) is None
