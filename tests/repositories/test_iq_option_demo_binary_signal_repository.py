from datetime import UTC, datetime

import pytest

from app.domain.candle import Candle
from app.domain.iq_option_binary_signal import IqOptionBinarySignal
from app.domain.trade_signal import TradeAction
from app.repositories.iq_option_demo_binary_signal_repository import (
    IqOptionDemoBinarySignalRepository,
)


def create_signal(
    action: TradeAction = TradeAction.CALL,
) -> IqOptionBinarySignal:
    return IqOptionBinarySignal(
        symbol="EURUSD-OTC",
        timeframe="1m",
        source="iq_option_demo",
        analysis_at=datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
        last_candle_open_time=datetime(2026, 11, 10, 12, 13, tzinfo=UTC),
        last_candle_close_time=datetime(2026, 11, 10, 12, 14, tzinfo=UTC),
        last_candle_age_seconds=30.0,
        reference_price=1.1000,
        reference_entry_time=datetime(2026, 11, 10, 12, 15, tzinfo=UTC),
        reference_expiration_time=datetime(
            2026,
            11,
            10,
            12,
            16,
            tzinfo=UTC,
        ),
        ema_fast=1.1002,
        ema_slow=1.0999,
        rsi=55.0,
        adx=25.0,
        atr=0.0005,
        action=action,
        reasons=("Technical reference only.",),
    )


def create_settlement_candle(close: float) -> Candle:
    return Candle(
        timestamp=datetime(2026, 11, 10, 12, 15, tzinfo=UTC),
        open=1.1000,
        high=max(1.1000, close),
        low=min(1.1000, close),
        close=close,
        volume=0.0,
    )


def test_saves_one_pending_reference_only_once_per_entry(
    tmp_path,
) -> None:
    repository = IqOptionDemoBinarySignalRepository(tmp_path)
    signal = create_signal()

    first_path = repository.save_pending(
        signal=signal,
        recorded_at=datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
    )
    repeated_path = repository.save_pending(
        signal=signal,
        recorded_at=datetime(2026, 11, 10, 12, 14, 50, tzinfo=UTC),
    )

    record = repository.get_record(first_path.stem)

    assert repeated_path == first_path
    assert record["analysis"]["action"] == "CALL"
    assert record["outcome"] == {
        "status": "PENDING",
        "settledAt": None,
        "settlementPrice": None,
    }


@pytest.mark.parametrize(
    ("action", "close", "expected_status"),
    [
        (TradeAction.CALL, 1.1005, "WIN"),
        (TradeAction.CALL, 1.0995, "LOSS"),
        (TradeAction.PUT, 1.0995, "WIN"),
        (TradeAction.PUT, 1.1005, "LOSS"),
        (TradeAction.CALL, 1.1000, "DRAW"),
    ],
)
def test_settles_due_reference_from_the_closed_entry_candle(
    tmp_path,
    action: TradeAction,
    close: float,
    expected_status: str,
) -> None:
    repository = IqOptionDemoBinarySignalRepository(tmp_path)
    record_path = repository.save_pending(
        signal=create_signal(action=action),
        recorded_at=datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
    )

    settled = repository.settle_due_references(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=(create_settlement_candle(close),),
        settled_at=datetime(2026, 11, 10, 12, 16, tzinfo=UTC),
    )

    assert settled == (
        {
            "recordId": record_path.stem,
            "status": expected_status,
            "settledAt": "2026-11-10T12:16:00+00:00",
            "settlementPrice": close,
        },
    )


def test_keeps_reference_pending_without_its_closed_entry_candle(
    tmp_path,
) -> None:
    repository = IqOptionDemoBinarySignalRepository(tmp_path)
    record_path = repository.save_pending(
        signal=create_signal(),
        recorded_at=datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
    )

    settled = repository.settle_due_references(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=(),
        settled_at=datetime(2026, 11, 10, 12, 16, tzinfo=UTC),
    )

    assert settled == ()
    assert repository.get_tracking(record_path.stem)["status"] == "PENDING"


def test_rejects_wait_references(tmp_path) -> None:
    repository = IqOptionDemoBinarySignalRepository(tmp_path)

    with pytest.raises(
        ValueError,
        match="only CALL and PUT references can be persisted",
    ):
        repository.save_pending(
            signal=create_signal(action=TradeAction.WAIT),
            recorded_at=datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
        )