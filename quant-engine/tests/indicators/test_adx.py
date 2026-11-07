from datetime import UTC, datetime, timedelta

import pytest

from app.domain.candle import Candle
from app.indicators.adx import calculate_adx


def create_trending_candles() -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    return tuple(
        Candle(
            timestamp=start + timedelta(minutes=index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.5 + index,
            close=100.5 + index,
            volume=0.0,
        )
        for index in range(7)
    )


def test_calculates_adx_for_a_directional_market() -> None:
    adx_values = calculate_adx(create_trending_candles(), 3)

    assert len(adx_values) == 2
    assert adx_values[-1] == pytest.approx(100.0)


@pytest.mark.parametrize("period", [0, -1, True, 1.5])
def test_rejects_invalid_period(period: object) -> None:
    with pytest.raises(ValueError, match="period"):
        calculate_adx(create_trending_candles(), period)  # type: ignore[arg-type]


def test_rejects_insufficient_candles() -> None:
    with pytest.raises(ValueError, match=r"2 \* period \+ 1"):
        calculate_adx(create_trending_candles()[:6], 3)

