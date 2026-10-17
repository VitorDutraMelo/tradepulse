from collections.abc import Sequence

from app.domain.candle import Candle


def calculate_ema(values: Sequence[float], period: int) -> list[float]:
    """Calculate the Exponential Moving Average (EMA)."""
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


def calculate_close_ema(candles: Sequence[Candle], period: int) -> list[float]:
    """Calculate EMA using the closing price of chronological candles."""
    close_prices = [candle.close for candle in candles]

    return calculate_ema(close_prices, period)