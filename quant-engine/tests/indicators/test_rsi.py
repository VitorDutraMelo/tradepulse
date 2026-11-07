from datetime import UTC, datetime

import pytest

from app.domain.candle import Candle
from app.indicators.rsi import calculate_close_rsi, calculate_rsi


def create_candle(hour: int, close: float) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, hour, tzinfo=UTC),
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=100.0,
    )


def test_calculates_rsi_from_wilder_average() -> None:
    result = calculate_rsi(
        [10.0, 8.0, 7.0, 12.0, 11.0],
        period=3,
    )

    assert result == pytest.approx([62.5, 52.63157895])


def test_returns_one_hundred_when_prices_only_rise() -> None:
    result = calculate_rsi([1.0, 2.0, 3.0, 4.0], period=3)

    assert result == [100.0]


def test_returns_zero_when_prices_only_fall() -> None:
    result = calculate_rsi([4.0, 3.0, 2.0, 1.0], period=3)

    assert result == [0.0]


def test_calculates_rsi_using_candle_closes() -> None:
    candles = [
        create_candle(0, 10.0),
        create_candle(1, 8.0),
        create_candle(2, 7.0),
        create_candle(3, 12.0),
    ]

    result = calculate_close_rsi(candles, period=3)

    assert result == pytest.approx([62.5])


@pytest.mark.parametrize("period", [0, -1])
def test_rejects_non_positive_period(period: int) -> None:
    with pytest.raises(ValueError, match="period must be greater than zero"):
        calculate_rsi([10.0, 11.0], period)


def test_rejects_insufficient_values() -> None:
    with pytest.raises(
        ValueError,
        match=r"values must contain at least `period \+ 1` items",
    ):
        calculate_rsi([10.0, 11.0, 12.0], period=3)


