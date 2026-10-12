from datetime import UTC, datetime

import pytest

from app.domain.candle import Candle


def test_creates_a_valid_candle() -> None:
    candle = Candle(
        timestamp=datetime(2026, 10, 7, 10, 0, tzinfo=UTC),
        open=100.0,
        high=105.0,
        low=98.0,
        close=103.0,
        volume=2500.0,
    )

    assert candle.timestamp == datetime(2026, 10, 7, 10, 0, tzinfo=UTC)
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 98.0
    assert candle.close == 103.0
    assert candle.volume == 2500.0


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("open", 0.0, "open must be greater than zero"),
        ("high", 0.0, "high must be greater than zero"),
        ("low", 0.0, "low must be greater than zero"),
        ("close", 0.0, "close must be greater than zero"),
        ("volume", -1.0, "volume cannot be negative"),
    ],
)
def test_rejects_invalid_numeric_values(
    field: str,
    value: float,
    message: str,
) -> None:
    candle_data = {
        "timestamp": datetime(2026, 10, 7, 10, 0, tzinfo=UTC),
        "open": 100.0,
        "high": 105.0,
        "low": 98.0,
        "close": 103.0,
        "volume": 2500.0,
    }
    candle_data[field] = value

    with pytest.raises(ValueError, match=message):
        Candle(**candle_data)


def test_rejects_a_timestamp_without_timezone() -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        Candle(
            timestamp=datetime(2026, 10, 7, 10, 0),
            open=100.0,
            high=105.0,
            low=98.0,
            close=103.0,
            volume=2500.0,
        )


def test_rejects_a_high_lower_than_low() -> None:
    with pytest.raises(ValueError, match="high cannot be lower than low"):
        Candle(
            timestamp=datetime(2026, 10, 7, 10, 0, tzinfo=UTC),
            open=100.0,
            high=97.0,
            low=98.0,
            close=99.0,
            volume=2500.0,
        )


def test_rejects_a_high_below_open_or_close() -> None:
    with pytest.raises(
        ValueError,
        match="high must be greater than or equal to open and close",
    ):
        Candle(
            timestamp=datetime(2026, 10, 7, 10, 0, tzinfo=UTC),
            open=100.0,
            high=99.0,
            low=98.0,
            close=101.0,
            volume=2500.0,
        )


def test_rejects_a_low_above_open_or_close() -> None:
    with pytest.raises(
        ValueError,
        match="low must be lower than or equal to open and close",
    ):
        Candle(
            timestamp=datetime(2026, 10, 7, 10, 0, tzinfo=UTC),
            open=100.0,
            high=105.0,
            low=101.0,
            close=103.0,
            volume=2500.0,
        )