from datetime import UTC, datetime

import pytest

from app.domain.candle import Candle
from app.indicators.ema import calculate_close_ema, calculate_ema


def create_candle(hour: int, close: float) -> Candle:
    open_price = 50.0

    return Candle(
        timestamp=datetime(2026, 1, 1, hour, tzinfo=UTC),
        open=open_price,
        high=max(open_price, close) + 1,
        low=min(open_price, close) - 1,
        close=close,
        volume=100.0,
    )


def test_calculates_ema_from_simple_moving_average_seed() -> None:
    values = [10.0, 11.0, 12.0, 13.0, 14.0]

    result = calculate_ema(values, period=3)

    assert result == pytest.approx([11.0, 12.0, 13.0])


def test_calculates_ema_using_candle_closing_prices() -> None:
    candles = [
        create_candle(hour=0, close=10.0),
        create_candle(hour=1, close=11.0),
        create_candle(hour=2, close=12.0),
        create_candle(hour=3, close=13.0),
        create_candle(hour=4, close=14.0),
    ]

    result = calculate_close_ema(candles, period=3)

    assert result == pytest.approx([11.0, 12.0, 13.0])


@pytest.mark.parametrize("period", [0, -1])
def test_rejects_invalid_period(period: int) -> None:
    with pytest.raises(ValueError, match="period must be greater than zero"):
        calculate_ema([10.0, 11.0, 12.0], period=period)


def test_rejects_insufficient_values() -> None:
    with pytest.raises(
        ValueError,
        match="values must contain at least `period` items",
    ):
        calculate_ema([10.0, 11.0], period=3)


def test_returns_one_value_when_values_match_period() -> None:
    result = calculate_ema([10.0, 20.0, 30.0], period=3)

    assert result == [20.0]