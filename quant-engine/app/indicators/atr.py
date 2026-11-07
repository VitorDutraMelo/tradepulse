from collections.abc import Sequence

from app.domain.candle import Candle


def calculate_atr(
    candles: Sequence[Candle],
    period: int,
) -> list[float]:
    """Calculate Wilder's Average True Range from chronological candles."""
    if isinstance(period, bool) or not isinstance(period, int):
        raise ValueError("period must be an integer")

    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(candles) < period + 1:
        raise ValueError(
            "candles must contain at least `period + 1` items"
        )

    true_ranges = [
        max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close),
        )
        for previous, current in zip(candles, candles[1:])
    ]

    atr = sum(true_ranges[:period]) / period
    atr_values = [atr]

    for true_range in true_ranges[period:]:
        atr = ((atr * (period - 1)) + true_range) / period
        atr_values.append(atr)

    return atr_values