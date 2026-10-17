from collections.abc import Sequence


def calculate_ema(values: Sequence[float], period: int) -> list[float]:
    """Calculate the Exponential Moving Average (EMA).

    The first EMA value is the Simple Moving Average (SMA) of the
    first `period` values. Each next value gives greater weight to
    the most recent price.

    Args:
        values: Numeric values in chronological order, oldest first.
        period: Number of values used by the indicator.

    Returns:
        EMA values beginning at the point where enough data exists.

    Raises:
        ValueError: If the period is invalid or there is insufficient data.
    """
    if period <= 0:
        raise ValueError("period must be greater than zero")

    if len(values) < period:
        raise ValueError("values must contain at least `period` items")

    multiplier = 2 / (period + 1)
    first_ema = sum(values[:period]) / period
    ema_values = [first_ema]

    for value in values[period:]:
        next_ema = (value - ema_values[-1]) * multiplier + ema_values[-1]
        ema_values.append(next_ema)

    return ema_values