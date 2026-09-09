from datetime import UTC, datetime, timedelta, timezone

from app.services.harmony import window_start


def test_sending_window_crosses_year_and_converts_to_utc() -> None:
    assert window_start(datetime(2026, 1, 1, tzinfo=UTC)) == datetime(
        2025, 8, 1, tzinfo=UTC
    )
    # Still September in New York; already October in UTC.
    assert window_start(
        datetime(2026, 9, 30, 21, tzinfo=timezone(timedelta(hours=-4)))
    ) == datetime(2026, 5, 1, tzinfo=UTC)
