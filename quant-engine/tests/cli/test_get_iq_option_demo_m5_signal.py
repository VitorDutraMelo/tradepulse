from datetime import UTC, datetime, timedelta

from app.cli.get_iq_option_demo_m5_signal import (
    evaluate_candidate,
    get_iq_option_demo_m5_signal,
)
from app.domain.candle import Candle


class StubProvider:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        return self._candles


def create_candles(count: int) -> tuple[Candle, ...]:
    start = datetime(2026, 11, 13, 0, 0, tzinfo=UTC)

    return tuple(
        Candle(
            timestamp=start + timedelta(minutes=index * 5),
            open=1.3000 + (index * 0.00001),
            high=1.3004 + (index * 0.00001),
            low=1.2996 + (index * 0.00001),
            close=1.3001 + (index * 0.00001),
            volume=0.0,
        )
        for index in range(count)
    )


def test_marks_insufficient_candles_as_wait() -> None:
    candles = create_candles(20)

    payload = get_iq_option_demo_m5_signal(
        symbol="GBPUSD-OTC",
        provider=StubProvider(candles),
        now=lambda: datetime(2026, 11, 13, 1, 40, tzinfo=UTC),
    )

    assert payload["decision"]["action"] == "WAIT"
    assert payload["decision"]["actionability"] == "DATA_INSUFFICIENT"
    assert payload["dataQuality"]["receivedClosedCandles"] == 20


def test_call_candidate_requires_all_confirmations() -> None:
    action, reasons = evaluate_candidate(
        close=1.2100,
        ema200=1.2000,
        rsi14=60.0,
        macd=0.003,
        macd_signal=0.002,
        histogram=0.001,
        previous_histogram=0.0005,
        adx14=25.0,
        atr14=0.010,
    )

    assert action == "CALL"
    assert reasons


def test_conflicting_rsi_returns_wait() -> None:
    action, reasons = evaluate_candidate(
        close=1.2100,
        ema200=1.2000,
        rsi14=75.0,
        macd=0.003,
        macd_signal=0.002,
        histogram=0.001,
        previous_histogram=0.0005,
        adx14=25.0,
        atr14=0.010,
    )

    assert action == "WAIT"
    assert any("RSI 14" in reason for reason in reasons)