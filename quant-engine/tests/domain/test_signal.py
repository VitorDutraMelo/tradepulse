from datetime import UTC, datetime

import pytest

from app.domain.signal import Signal, SignalDirection


def create_valid_signal(**overrides: object) -> Signal:
    values: dict[str, object] = {
        "symbol": "BTC-USD",
        "timeframe": "1h",
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "direction": SignalDirection.LONG,
        "score": 70,
        "reasons": ("EMA 9 crossed above EMA 21",),
    }
    values.update(overrides)

    return Signal(**values)  # type: ignore[arg-type]


def test_creates_valid_signal() -> None:
    signal = create_valid_signal()

    assert signal.symbol == "BTC-USD"
    assert signal.timeframe == "1h"
    assert signal.direction is SignalDirection.LONG
    assert signal.score == 70
    assert signal.reasons == ("EMA 9 crossed above EMA 21",)


@pytest.mark.parametrize("score", [-1, 101])
def test_rejects_score_outside_range(score: int) -> None:
    with pytest.raises(ValueError, match="score must be between 0 and 100"):
        create_valid_signal(score=score)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("symbol", "   ", "symbol must not be empty"),
        ("timeframe", "", "timeframe must not be empty"),
    ],
)
def test_rejects_empty_identification_fields(
    field_name: str,
    value: str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        create_valid_signal(**{field_name: value})


def test_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
        create_valid_signal(timestamp=datetime(2026, 1, 1))


def test_rejects_direction_outside_enum() -> None:
    with pytest.raises(ValueError, match="direction must be a SignalDirection"):
        create_valid_signal(direction="BUY")


def test_rejects_empty_reasons() -> None:
    with pytest.raises(ValueError, match="reasons must contain at least one item"):
        create_valid_signal(reasons=())


def test_rejects_blank_reason() -> None:
    with pytest.raises(ValueError, match="reasons must not contain empty items"):
        create_valid_signal(reasons=("Valid reason", "   "))