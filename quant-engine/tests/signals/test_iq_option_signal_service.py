from datetime import UTC, datetime

from app.domain.signal import Signal, SignalDirection
from app.domain.trade_signal import MarketCategory, TradeAction
from app.signals.iq_option_signal_service import IqOptionSignalService


def create_analysis(direction: SignalDirection) -> Signal:
    return Signal(
        symbol="BTC-USD",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        direction=direction,
        score=70,
        reasons=("EMA 9 crossed above EMA 21",),
    )


def test_prepares_wait_for_long_analysis_without_automatic_call_mapping() -> None:
    signal = IqOptionSignalService().prepare(
        analysis=create_analysis(SignalDirection.LONG),
        market=MarketCategory.CRYPTO,
        data_source="binance_spot",
    )

    assert signal.action is TradeAction.WAIT
    assert signal.analysis_direction is SignalDirection.LONG
    assert signal.entry_time is None
    assert signal.expiration_time is None
    assert signal.reasons == (
        "EMA 9 crossed above EMA 21",
        (
            "No IQ Option policy is configured for this market and data "
            "source; manual action remains WAIT."
        ),
    )


def test_prepares_wait_for_short_analysis_without_automatic_put_mapping() -> None:
    signal = IqOptionSignalService().prepare(
        analysis=create_analysis(SignalDirection.SHORT),
        market=MarketCategory.CRYPTO,
        data_source="binance_spot",
    )

    assert signal.action is TradeAction.WAIT
    assert signal.analysis_direction is SignalDirection.SHORT