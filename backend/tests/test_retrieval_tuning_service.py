import uuid
from datetime import datetime

from app.models.feedback import Feedback, FeedbackRating
from app.services.retrieval_tuning_service import compute_candidate


def _feedback(*, rating: FeedbackRating, citations: list[dict] | None) -> Feedback:
    return Feedback(
        id=uuid.uuid4(),
        session_id=uuid.uuid4(),
        message_id="msg",
        question="q",
        answer="a",
        rating=rating,
        comment=None,
        topic=None,
        citations=citations,
        created_at=datetime.now(),
    )


def _row(rating: FeedbackRating, rerank_score: float) -> Feedback:
    return _feedback(
        rating=rating,
        citations=[{"url": "https://example.illinois.edu", "rerank_score": rerank_score}],
    )


def test_below_min_samples_returns_no_candidate() -> None:
    rows = [_row(FeedbackRating.NOT_HELPFUL, 0.1) for _ in range(19)]

    result = compute_candidate(1.0, rows, min_samples=20)

    assert result.reason == "insufficient_samples"
    assert result.candidate_value is None
    assert result.sample_size == 19


def test_rows_with_no_citations_or_no_rerank_score_are_excluded_from_sample_size() -> None:
    eligible = [_row(FeedbackRating.NOT_HELPFUL, 0.1) for _ in range(20)]
    no_citations = [_feedback(rating=FeedbackRating.NOT_HELPFUL, citations=None) for _ in range(5)]
    no_rerank_score = [
        _feedback(
            rating=FeedbackRating.NOT_HELPFUL,
            citations=[{"url": "https://example.illinois.edu", "rerank_score": None}],
        )
        for _ in range(5)
    ]

    result = compute_candidate(1.0, eligible + no_citations + no_rerank_score, min_samples=20)

    assert result.sample_size == 20


def test_flag_rate_below_threshold_returns_no_signal() -> None:
    # 2/20 = 10% near-floor negatives, below the default 15% threshold.
    rows = [_row(FeedbackRating.NOT_HELPFUL, 0.1) for _ in range(2)] + [
        _row(FeedbackRating.HELPFUL, 5.0) for _ in range(18)
    ]

    result = compute_candidate(1.0, rows, min_samples=20, flag_rate_threshold=0.15)

    assert result.reason == "no_signal"
    assert result.candidate_value is None
    assert result.flag_rate == 0.1


def test_flag_rate_at_or_above_threshold_proposes_a_stepped_up_candidate() -> None:
    # 3/20 = 15%, exactly at the default threshold.
    rows = [_row(FeedbackRating.NOT_HELPFUL, 0.1) for _ in range(3)] + [
        _row(FeedbackRating.HELPFUL, 5.0) for _ in range(17)
    ]

    result = compute_candidate(1.0, rows, min_samples=20, flag_rate_threshold=0.15, step_size=0.25)

    assert result.reason == "candidate"
    assert result.candidate_value == 1.25


def test_helpful_ratings_near_the_floor_dont_count_as_flags() -> None:
    # Only NOT_HELPFUL ratings count toward flag_rate -- a helpful answer
    # whose citation happened to score near the floor isn't evidence the
    # floor is wrong.
    rows = [_row(FeedbackRating.HELPFUL, 0.1) for _ in range(20)]

    result = compute_candidate(1.0, rows, min_samples=20, flag_rate_threshold=0.15)

    assert result.reason == "no_signal"
    assert result.flag_rate == 0.0


def test_proximity_margin_catches_scores_approaching_not_just_below_the_floor() -> None:
    # current_value=1.0, proximity_margin=1.0 -> anything under 2.0 flags.
    rows = [_row(FeedbackRating.NOT_HELPFUL, 1.9) for _ in range(5)] + [
        _row(FeedbackRating.HELPFUL, 5.0) for _ in range(15)
    ]

    result = compute_candidate(
        1.0, rows, min_samples=20, flag_rate_threshold=0.15, proximity_margin=1.0
    )

    assert result.reason == "candidate"


def test_candidate_value_is_capped_at_max_value() -> None:
    rows = [_row(FeedbackRating.NOT_HELPFUL, 0.1) for _ in range(20)]

    result = compute_candidate(
        2.9, rows, min_samples=20, flag_rate_threshold=0.15, step_size=0.25, max_value=3.0
    )

    assert result.reason == "candidate"
    assert result.candidate_value == 3.0
