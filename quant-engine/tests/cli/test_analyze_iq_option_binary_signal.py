from datetime import UTC, datetime
from pathlib import Path

from app.cli.analyze_iq_option_binary_signal import (
    analyze_iq_option_binary_signal,
)
from app.domain.candle import Candle
from app.domain.iq_option_binary_signal import IqOptionBinarySignal
from app.domain.trade_signal import TradeAction
from app.repositories.iq_option_demo_binary_signal_repository import (
    IqOptionDemoBinarySignalRepository,
)


class StubProvider:
    source = "iq_option_demo"

    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        return self._candles


class StubStrategy:
    def __init__(self, signal: IqOptionBinarySignal) -> None:
        self._signal = signal

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        candles: tuple[Candle, ...],
        source: str,
        analysis_at: datetime,
    ) -> IqOptionBinarySignal:
        return self._signal


def create_signal() -> IqOptionBinarySignal:
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
        action=TradeAction.CALL,
        reasons=("Technical reference only.",),
    )


def create_wait_signal() -> IqOptionBinarySignal:
    return IqOptionBinarySignal(
        symbol="EURUSD-OTC",
        timeframe="1m",
        source="iq_option_demo",
        analysis_at=datetime(2026, 11, 10, 12, 16, tzinfo=UTC),
        last_candle_open_time=datetime(2026, 11, 10, 12, 15, tzinfo=UTC),
        last_candle_close_time=datetime(2026, 11, 10, 12, 16, tzinfo=UTC),
        last_candle_age_seconds=0.0,
        reference_price=1.1005,
        reference_entry_time=datetime(2026, 11, 10, 12, 17, tzinfo=UTC),
        reference_expiration_time=datetime(
            2026,
            11,
            10,
            12,
            18,
            tzinfo=UTC,
        ),
        ema_fast=1.1000,
        ema_slow=1.1000,
        rsi=50.0,
        adx=10.0,
        atr=0.0005,
        action=TradeAction.WAIT,
        reasons=("ADX 14 is below the configured minimum trend strength.",),
    )


def create_settlement_candle() -> Candle:
    return Candle(
        timestamp=datetime(2026, 11, 10, 12, 15, tzinfo=UTC),
        open=1.1000,
        high=1.1005,
        low=1.1000,
        close=1.1005,
        volume=0.0,
    )


def test_returns_pending_tracking_for_a_new_call_reference(
    tmp_path: Path,
) -> None:
    payload = analyze_iq_option_binary_signal(
        symbol="EURUSD-OTC",
        timeframe="1m",
        limit=100,
        max_candle_age_seconds=120,
        provider=StubProvider(()),
        analysis_repository=IqOptionDemoBinarySignalRepository(tmp_path),
        now=lambda: datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
        strategy=StubStrategy(create_signal()),
    )

    assert payload["action"] == "CALL"
    assert payload["tracking"]["status"] == "PENDING"
    assert payload["tracking"]["recordId"] is not None


def test_settles_existing_reference_when_its_candle_is_closed(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoBinarySignalRepository(tmp_path)
    signal = create_signal()

    repository.save_pending(
        signal,
        datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
    )

    payload = analyze_iq_option_binary_signal(
        symbol="EURUSD-OTC",
        timeframe="1m",
        limit=100,
        max_candle_age_seconds=120,
        provider=StubProvider((create_settlement_candle(),)),
        analysis_repository=repository,
        now=lambda: datetime(2026, 11, 10, 12, 16, tzinfo=UTC),
        strategy=StubStrategy(signal),
    )

    assert payload["tracking"]["status"] == "WIN"
    assert payload["tracking"]["settlementPrice"] == 1.1005


def test_settles_pending_reference_even_when_current_analysis_is_wait(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoBinarySignalRepository(tmp_path)

    pending_record_path = repository.save_pending(
        create_signal(),
        datetime(2026, 11, 10, 12, 14, 30, tzinfo=UTC),
    )

    payload = analyze_iq_option_binary_signal(
        symbol="EURUSD-OTC",
        timeframe="1m",
        limit=100,
        max_candle_age_seconds=120,
        provider=StubProvider((create_settlement_candle(),)),
        analysis_repository=repository,
        now=lambda: datetime(2026, 11, 10, 12, 16, tzinfo=UTC),
        strategy=StubStrategy(create_wait_signal()),
    )

    settled_tracking = repository.get_tracking(pending_record_path.stem)

    assert payload["action"] == "WAIT"
    assert payload["tracking"]["status"] == "NOT_APPLICABLE"
    assert settled_tracking["status"] == "WIN"
    assert settled_tracking["settlementPrice"] == 1.1005