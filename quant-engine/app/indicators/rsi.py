from collections.abc import Sequence

from app.domain.candle import Candle


def calculate_rsi(values: Sequence[float], period: int) -> list[float]:
    """Calculate Wilder's Relative Strength Index (RSI)."""
    if isinstance(period, bool) or not isinstance(period, int):
        raise ValueError("period must be an integer")

    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(values) < period + 1:
        raise ValueError(
            "values must contain at least `period + 1` items"
        )

    changes = [
        current_value - previous_value
        for previous_value, current_value in zip(values, values[1:])
    ]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    rsi_values = [_calculate_rsi_value(average_gain, average_loss)]

    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
        rsi_values.append(_calculate_rsi_value(average_gain, average_loss))

    return rsi_values


def calculate_close_rsi(
    candles: Sequence[Candle],
    period: int,
) -> list[float]:
    """Calculate RSI using closing prices from chronological candles."""
    return calculate_rsi(
        [candle.close for candle in candles],
        period,
    )


def _calculate_rsi_value(average_gain: float, average_loss: float) -> float:
    if average_loss == 0:
        return 100.0

    if average_gain == 0:
        return 0.0

    relative_strength = average_gain / average_loss

    return 100 - (100 / (1 + relative_strength))
