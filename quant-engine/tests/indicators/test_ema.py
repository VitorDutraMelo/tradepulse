import pytest

from app.indicators.ema import calculate_ema


def test_calculates_ema_from_simple_moving_average_seed() -> None:
    values = [10.0, 11.0, 12.0, 13.0, 14.0]

    result = calculate_ema(values, period=3)

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