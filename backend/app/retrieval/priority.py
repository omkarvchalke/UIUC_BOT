"""Computes Document.authority_score / Document.retrieval_priority.

Deliberately NOT a copy of Source Manifest V2's literal per-row values: V2's own
`authority_score` is a flat 10 for the overwhelming majority of its ~1,069 rows regardless of
role, which would make the field useless as the ranking signal Source Manifest V2's own Part 4
asks for ("authority_score should represent the reliability/authority of the source"). Instead
both fields are derived here from source_type/source_role/temporal_scope via a small, explicit,
documented formula -- which is really just making explicit the ordering V2's own retrieval_priority
numbers already showed implicitly per row (e.g. its historical commencement-ceremony pages sit at
priority 40 against 81-95 for current pages; MTD's authorized_external rows sit at authority
9/priority 75 against 10/81-95 for uiuc_official).

Called by scripts/remap_topics_v2.py (existing corpus) and IngestionService (new ingestion).
"""

from app.models.document import IndexStatus, SourceRole, SourceType, TemporalScope

# Expected general hierarchy (Source Manifest V2, Part 4): official UIUC source > explicitly
# authorized external source > other approved source. Only two source_type values exist today,
# so this is a two-entry table, not a formula -- easy to extend if a third tier is ever added.
_AUTHORITY_BY_SOURCE_TYPE: dict[SourceType, int] = {
    SourceType.HTML: 10,
    SourceType.PDF: 10,
}

# Baseline retrieval_priority by source_role, before the temporal_scope adjustment below.
# Ordering mirrors what a UIUC student actually needs surfaced first: hard deadlines and
# binding policy outrank general reference/directory pages, which outrank pages that are
# explicitly about the past.
_PRIORITY_BY_ROLE: dict[SourceRole, int] = {
    SourceRole.DEADLINE: 95,
    SourceRole.POLICY: 90,
    SourceRole.PROCEDURE: 88,
    SourceRole.PROGRAM: 85,
    SourceRole.COURSE: 84,
    SourceRole.SERVICE: 83,
    SourceRole.NEWS: 81,
    SourceRole.REFERENCE: 80,
    SourceRole.DIRECTORY: 78,
    SourceRole.HISTORICAL: 60,
}
_PRIORITY_DEFAULT = 80  # source_role is None / not confidently known -- same tier as REFERENCE.

_TEMPORAL_PENALTY: dict[TemporalScope, int] = {
    TemporalScope.HISTORICAL: 40,
    TemporalScope.ARCHIVE: 40,
    TemporalScope.CURRENT: 0,
    TemporalScope.UNSPECIFIED: 0,
}


def compute_authority_score(source_type: SourceType, *, authorized_external: bool = False) -> int:
    """authorized_external: True for sources explicitly marked authorized_external in Source
    Manifest V2 (today: MTD, for transportation) -- not derivable from SourceType alone, since
    SourceType is about file format (HTML/PDF), not institutional authority. Callers that know a
    source is authorized-external-but-not-UIUC pass this explicitly; everything else defaults to
    the UIUC-official tier."""
    base = _AUTHORITY_BY_SOURCE_TYPE.get(source_type, 10)
    return 8 if authorized_external else base


def compute_retrieval_priority(
    source_role: SourceRole | None, temporal_scope: TemporalScope | None
) -> int:
    base = _PRIORITY_BY_ROLE.get(source_role, _PRIORITY_DEFAULT) if source_role else _PRIORITY_DEFAULT
    penalty = _TEMPORAL_PENALTY.get(temporal_scope, 0) if temporal_scope else 0
    return max(0, min(100, base - penalty))


def priority_multiplier(retrieval_priority: int | None, *, boost_range: float) -> float:
    """Normalizes a 0-100 retrieval_priority into a [1 - boost_range, 1 + boost_range]
    multiplier for HybridRetriever._fuse -- a boost, not an override (Source Manifest V2, Part
    4). A null priority (not yet computed/backfilled) is treated as the neutral midpoint (50),
    i.e. multiplier 1.0 -- unscored chunks are neither penalized nor favored relative to today's
    behavior."""
    value = retrieval_priority if retrieval_priority is not None else 50
    normalized = max(0.0, min(1.0, value / 100))
    return (1 - boost_range) + normalized * (2 * boost_range)


def is_retrievable(index_status: IndexStatus | None) -> bool:
    """Only APPROVED sources participate in normal retrieval (Source Manifest V2, Part 7). A
    null index_status (rows from before this column existed, not yet backfilled) is treated as
    approved -- the pre-V2 default behavior was "every ingested document is retrievable," and a
    null value must not silently make existing documents disappear from search results."""
    return index_status is None or index_status == IndexStatus.APPROVED
