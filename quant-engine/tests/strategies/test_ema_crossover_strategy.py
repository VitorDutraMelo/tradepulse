from datetime import UTC, datetime, timedelta

import pytest

from app.domain.candle import Candle
from app.domain.signal import SignalDirection
from app.strategies.ema_crossover_strategy import EmaCrossoverStrategy


def create_candles(close_prices: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    return [
        Candle(
            timestamp=start + timedelta(hours=index),
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=100.0,
        )
        for index, close in enumerate(close_prices)
    ]


def test_returns_long_when_fast_ema_crosses_above_slow_ema() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    candles = create_candles([10.0, 8.0, 7.0, 12.0])

    signal = strategy.analyze("BTC-USD", "1h", candles)

    assert signal.direction is SignalDirection.LONG
    assert signal.score == 70
    assert signal.reasons == ("EMA 2 crossed above EMA 3",)


def test_returns_short_when_fast_ema_crosses_below_slow_ema() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    candles = create_candles([10.0, 12.0, 13.0, 8.0])

    signal = strategy.analyze("BTC-USD", "1h", candles)

    assert signal.direction is SignalDirection.SHORT
    assert signal.score == 70
    assert signal.reasons == ("EMA 2 crossed below EMA 3",)


def test_returns_neutral_when_no_crossover_happens() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    candles = create_candles([10.0, 8.0, 7.0, 6.0])

    signal = strategy.analyze("BTC-USD", "1h", candles)

    assert signal.direction is SignalDirection.NEUTRAL
    assert signal.score == 20


def test_returns_neutral_when_there_is_insufficient_data() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)
    candles = create_candles([10.0, 8.0, 7.0])

    signal = strategy.analyze("BTC-USD", "1h", candles)

    assert signal.direction is SignalDirection.NEUTRAL
    assert signal.score == 0
    assert "Insufficient data" in signal.reasons[0]


def test_rejects_empty_candle_sequence() -> None:
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)

    with pytest.raises(ValueError, match="candles must contain at least one item"):
        strategy.analyze("BTC-USD", "1h", [])


@pytest.mark.parametrize(
    ("fast_period", "slow_period"),
    [
        (0, 3),
        (2, 0),
    ],
)
def test_rejects_non_positive_periods(
    fast_period: int,
    slow_period: int,
) -> None:
    with pytest.raises(ValueError, match="periods must be greater than zero"):
        EmaCrossoverStrategy(fast_period=fast_period, slow_period=slow_period)


def test_rejects_fast_period_greater_than_or_equal_to_slow_period() -> None:
    with pytest.raises(
        ValueError,
        match="fast_period must be smaller than slow_period",
    ):
        EmaCrossoverStrategy(fast_period=3, slow_period=3)