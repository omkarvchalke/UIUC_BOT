from datetime import UTC, datetime, timedelta, timezone

from app.ingestion.timestamps import ensure_utc


def test_none_stays_none() -> None:
    assert ensure_utc(None) is None


def test_naive_datetime_gets_utc_attached() -> None:
    naive = datetime(2026, 3, 15, 10, 0)
    result = ensure_utc(naive)
    assert result == datetime(2026, 3, 15, 10, 0, tzinfo=UTC)


def test_already_aware_datetime_is_left_untouched() -> None:
    aware = datetime(2026, 3, 15, 10, 0, tzinfo=timezone(timedelta(hours=-5)))
    result = ensure_utc(aware)
    assert result is aware
