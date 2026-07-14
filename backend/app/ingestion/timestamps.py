from datetime import UTC, datetime


def ensure_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime; leave an already-aware one untouched.

    Source metadata is inconsistent about including a timezone offset. The
    `last_updated` column is `timestamptz`, and asyncpg errors if handed a
    naive datetime there -- so every loader normalizes through this before
    returning, rather than each guessing independently.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
