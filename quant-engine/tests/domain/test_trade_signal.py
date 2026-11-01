from datetime import UTC, datetime, timedelta

import pytest

from app.domain.signal import SignalDirection
from app.domain.trade_signal import (
    MarketCategory,
    SignalPlatform,
    TradeAction,
    TradeSignal,
)


def create_valid_trade_signal(**overrides: object) -> TradeSignal:
    values: dict[str, object] = {
        "platform": SignalPlatform.IQ_OPTION,
        "asset": "BTC-USD",
        "market": MarketCategory.CRYPTO,
        "timeframe": "1h",
        "timestamp": datetime(2026, 1, 1, tzinfo=UTC),
        "data_source": "binance_spot",
        "analysis_direction": SignalDirection.LONG,
        "action": TradeAction.WAIT,
        "entry_time": None,
        "expiration_time": None,
        "reasons": ("No IQ Option policy is configured.",),
    }
    values.update(overrides)

    return TradeSignal(**values)  # type: ignore[arg-type]


def test_creates_valid_wait_signal() -> None:
    signal = create_valid_trade_signal()

    assert signal.platform is SignalPlatform.IQ_OPTION
    assert signal.action is TradeAction.WAIT
    assert signal.analysis_direction is SignalDirection.LONG
    assert signal.entry_time is None
    assert signal.expiration_time is None


def test_creates_valid_call_signal_with_schedule() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    entry_time = timestamp + timedelta(minutes=5)
    expiration_time = entry_time + timedelta(minutes=5)

    signal = create_valid_trade_signal(
        action=TradeAction.CALL,
        entry_time=entry_time,
        expiration_time=expiration_time,
    )

    assert signal.action is TradeAction.CALL
    assert signal.entry_time == entry_time
    assert signal.expiration_time == expiration_time


def test_rejects_wait_signal_with_schedule() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)

    with pytest.raises(
        ValueError,
        match="WAIT signals must not define entry or expiration times",
    ):
        create_valid_trade_signal(
            entry_time=timestamp,
            expiration_time=timestamp + timedelta(minutes=5),
        )


@pytest.mark.parametrize("action", [TradeAction.CALL, TradeAction.PUT])
def test_rejects_actionable_signal_without_schedule(action: TradeAction) -> None:
    with pytest.raises(
        ValueError,
        match="CALL and PUT signals require entry and expiration times",
    ):
        create_valid_trade_signal(action=action)


def test_rejects_expiration_not_after_entry() -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC)
    entry_time = timestamp + timedelta(minutes=5)

    with pytest.raises(ValueError, match="expiration_time must be after entry_time"):
        create_valid_trade_signal(
            action=TradeAction.PUT,
            entry_time=entry_time,
            expiration_time=entry_time,
        )


def test_rejects_analysis_direction_outside_enum() -> None:
    with pytest.raises(
        ValueError,
        match="analysis_direction must be a SignalDirection",
    ):
        create_valid_trade_signal(analysis_direction="CALL")