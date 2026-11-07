from datetime import UTC, datetime, timedelta

import pytest

from app.domain.candle import Candle
from app.indicators.atr import calculate_atr


def create_candles() -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    return tuple(
        Candle(
            timestamp=start + timedelta(minutes=index),
            open=close - 0.5,
            high=close + 1.0,
            low=close - 1.0,
            close=close,
            volume=0.0,
        )
        for index, close in enumerate([10.0, 11.0, 12.0, 13.0])
    )


def test_calculates_wilder_atr() -> None:
    assert calculate_atr(create_candles(), 2) == [2.0, 2.0]


@pytest.mark.parametrize("period", [0, -1, True, 1.5])
def test_rejects_invalid_period(period: object) -> None:
    with pytest.raises(ValueError, match="period"):
        calculate_atr(create_candles(), period)  # type: ignore[arg-type]


def test_rejects_insufficient_candles() -> None:
    with pytest.raises(ValueError, match=r"period \+ 1"):
        calculate_atr(create_candles()[:2], 2)
