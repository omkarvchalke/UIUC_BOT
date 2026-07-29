"""Pure decision logic for automatic retrieval-parameter tuning
(scripts/tune_retrieval_params.py). No I/O here -- the script does the DB
reads/writes and the golden-set gate; this module only decides, from
already-fetched feedback, whether a candidate value is even worth
evaluating against that gate.

See the plan this implements: `_MIN_RERANK_SCORE_DEFAULT`
(app/graph/generation.py) was picked by eyeballing one live example. This
uses accumulated thumbs-down feedback whose cited chunks scored near the
current floor as the signal that the floor may need to rise -- deliberately
raise-only (see compute_candidate's docstring) and gated on a minimum
sample size so a handful of ratings can't move it.
"""

from dataclasses import dataclass
from typing import Any

from app.models.feedback import Feedback, FeedbackRating

# Chosen because it's roughly 1-2x a plausible single week of real traffic
# for this app (feedback volume is low -- see the plan). Below this many
# eligible rows, there simply isn't enough signal to safely tune anything.
DEFAULT_MIN_SAMPLES = 20
# Small relative to the ~5-point gap between the bad (0.48) and good
# (5.2-8.3) scores in the live example that justified this knob at all --
# one adjustment can't leap anywhere near an extreme.
DEFAULT_STEP_SIZE = 0.25
# Fraction of eligible feedback that must be a "near-floor negative" (see
# compute_candidate) before raising the floor is even considered.
DEFAULT_FLAG_RATE_THRESHOLD = 0.15
# A negative row's minimum citation rerank_score counts as "near the floor"
# if it's within this margin above current_value -- catches scores
# approaching the floor, not just already below it.
DEFAULT_PROXIMITY_MARGIN = 1.0
# Ceiling on any auto-raised value, comfortably below the 5.2 floor of
# good-chunk scores observed live -- no sequence of automatic raises can
# ever climb into territory that would exclude chunks like those.
DEFAULT_MAX_VALUE = 3.0


@dataclass(frozen=True)
class TuningCandidate:
    current_value: float
    # None means "don't propose anything" -- see `reason` for why.
    candidate_value: float | None
    sample_size: int
    flag_rate: float | None
    reason: str  # "insufficient_samples" | "no_signal" | "candidate"


def _min_citation_rerank_score(citations: list[dict[str, Any]] | None) -> float | None:
    if not citations:
        return None
    scores = [c["rerank_score"] for c in citations if c.get("rerank_score") is not None]
    if not scores:
        return None
    return float(min(scores))


def compute_candidate(
    current_value: float,
    feedback_rows: list[Feedback],
    *,
    min_samples: int = DEFAULT_MIN_SAMPLES,
    step_size: float = DEFAULT_STEP_SIZE,
    flag_rate_threshold: float = DEFAULT_FLAG_RATE_THRESHOLD,
    proximity_margin: float = DEFAULT_PROXIMITY_MARGIN,
    max_value: float = DEFAULT_MAX_VALUE,
) -> TuningCandidate:
    """Decides whether enough evidence exists to propose raising
    `current_value`, from feedback rows already fetched (e.g. via
    FeedbackRepository.list_since).

    Deliberately raise-only: the only evidence this has is "a rated-down
    answer cited a chunk that scored near or below the current floor",
    which only justifies raising it. There's no live evidence yet
    justifying a symmetric auto-lower policy, so this never proposes
    lowering `current_value`.

    Rows with no citations, or citations with no rerank_score (e.g. rows
    from before this data was captured, or from the Groq answer path which
    doesn't populate rerank_score at all -- see app/schemas/chat.py), carry
    no signal and are excluded from both the sample-size count and the
    flag-rate calculation, not treated as zero/negative signal.
    """
    eligible: list[tuple[FeedbackRating, float]] = []
    for row in feedback_rows:
        score = _min_citation_rerank_score(row.citations)
        if score is None:
            continue
        eligible.append((row.rating, score))

    sample_size = len(eligible)
    if sample_size < min_samples:
        return TuningCandidate(
            current_value=current_value,
            candidate_value=None,
            sample_size=sample_size,
            flag_rate=None,
            reason="insufficient_samples",
        )

    near_floor_negatives = sum(
        1
        for rating, score in eligible
        if rating == FeedbackRating.NOT_HELPFUL and score < current_value + proximity_margin
    )
    flag_rate = near_floor_negatives / sample_size

    if flag_rate < flag_rate_threshold:
        return TuningCandidate(
            current_value=current_value,
            candidate_value=None,
            sample_size=sample_size,
            flag_rate=flag_rate,
            reason="no_signal",
        )

    candidate_value = min(current_value + step_size, max_value)
    return TuningCandidate(
        current_value=current_value,
        candidate_value=candidate_value,
        sample_size=sample_size,
        flag_rate=flag_rate,
        reason="candidate",
    )
