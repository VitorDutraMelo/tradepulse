from collections.abc import Sequence

from app.domain.candle import Candle


def calculate_adx(
    candles: Sequence[Candle],
    period: int,
) -> list[float]:
    """Calculate Wilder's Average Directional Index from chronological candles."""
    if isinstance(period, bool) or not isinstance(period, int):
        raise ValueError("period must be an integer")

    if period <= 0:
        raise ValueError("period must be greater than zero")

    required_candles = (period * 2) + 1

    if len(candles) < required_candles:
        raise ValueError(
            "candles must contain at least `2 * period + 1` items"
        )

    true_ranges: list[float] = []
    positive_directional_movements: list[float] = []
    negative_directional_movements: list[float] = []

    for previous, current in zip(candles, candles[1:]):
        upward_move = current.high - previous.high
        downward_move = previous.low - current.low

        positive_directional_movement = (
            upward_move
            if upward_move > downward_move and upward_move > 0
            else 0.0
        )
        negative_directional_movement = (
            downward_move
            if downward_move > upward_move and downward_move > 0
            else 0.0
        )

        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
        positive_directional_movements.append(
            positive_directional_movement
        )
        negative_directional_movements.append(
            negative_directional_movement
        )

    smoothed_true_range = sum(true_ranges[:period])
    smoothed_positive_movement = sum(
        positive_directional_movements[:period]
    )
    smoothed_negative_movement = sum(
        negative_directional_movements[:period]
    )

    directional_index_values = [
        _directional_index(
            smoothed_true_range,
            smoothed_positive_movement,
            smoothed_negative_movement,
        )
    ]

    for index in range(period, len(true_ranges)):
        smoothed_true_range = (
            smoothed_true_range
            - (smoothed_true_range / period)
            + true_ranges[index]
        )
        smoothed_positive_movement = (
            smoothed_positive_movement
            - (smoothed_positive_movement / period)
            + positive_directional_movements[index]
        )
        smoothed_negative_movement = (
            smoothed_negative_movement
            - (smoothed_negative_movement / period)
            + negative_directional_movements[index]
        )

        directional_index_values.append(
            _directional_index(
                smoothed_true_range,
                smoothed_positive_movement,
                smoothed_negative_movement,
            )
        )

    adx = sum(directional_index_values[:period]) / period
    adx_values = [adx]

    for directional_index in directional_index_values[period:]:
        adx = ((adx * (period - 1)) + directional_index) / period
        adx_values.append(adx)

    return adx_values


def _directional_index(
    smoothed_true_range: float,
    smoothed_positive_movement: float,
    smoothed_negative_movement: float,
) -> float:
    if smoothed_true_range == 0:
        return 0.0

    positive_directional_indicator = (
        100 * smoothed_positive_movement / smoothed_true_range
    )
    negative_directional_indicator = (
        100 * smoothed_negative_movement / smoothed_true_range
    )
    denominator = (
        positive_directional_indicator + negative_directional_indicator
    )

    if denominator == 0:
        return 0.0

    return (
        100
        * abs(
            positive_directional_indicator
            - negative_directional_indicator
        )
        / denominator
    )