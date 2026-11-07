from datetime import UTC, datetime, timedelta

from app.domain.candle import Candle
from app.domain.trade_signal import TradeAction
from app.strategies.iq_option_trend_strategy import IqOptionTrendStrategy


def create_candles(closes: list[float]) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    return tuple(
        Candle(
            timestamp=start + timedelta(minutes=index),
            open=close - 0.1,
            high=close + 0.2,
            low=close - 0.2,
            close=close,
            volume=0.0,
        )
        for index, close in enumerate(closes)
    )


def create_permissive_strategy() -> IqOptionTrendStrategy:
    return IqOptionTrendStrategy(
        minimum_adx=0.0,
        minimum_ema_atr_ratio=0.0,
        call_rsi_minimum=0.0,
        call_rsi_maximum=100.0,
        put_rsi_minimum=0.0,
        put_rsi_maximum=100.0,
    )


def analysis_time_for(candles: tuple[Candle, ...]) -> datetime:
    return candles[-1].timestamp + timedelta(minutes=1, seconds=5)


def test_returns_call_for_a_confirmed_upward_trend() -> None:
    candles = create_candles([100.0 + index for index in range(29)])

    signal = create_permissive_strategy().analyze(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=candles,
        source="iq_option_demo",
        analysis_at=analysis_time_for(candles),
    )

    assert signal.action is TradeAction.CALL
    assert signal.ema_fast is not None
    assert signal.ema_slow is not None
    assert signal.ema_fast > signal.ema_slow
    assert signal.reference_entry_time == (
        candles[-1].timestamp + timedelta(minutes=2)
    )
    assert signal.reference_expiration_time == (
        candles[-1].timestamp + timedelta(minutes=3)
    )


def test_returns_put_for_a_confirmed_downward_trend() -> None:
    candles = create_candles([200.0 - index for index in range(29)])

    signal = create_permissive_strategy().analyze(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=candles,
        source="iq_option_demo",
        analysis_at=analysis_time_for(candles),
    )

    assert signal.action is TradeAction.PUT
    assert signal.ema_fast is not None
    assert signal.ema_slow is not None
    assert signal.ema_fast < signal.ema_slow


def test_returns_wait_when_ema_separation_is_too_small() -> None:
    candles = create_candles(
        [100.0 + (0.02 if index % 2 else 0.0) for index in range(29)]
    )
    strategy = IqOptionTrendStrategy(
        minimum_adx=0.0,
        minimum_ema_atr_ratio=10.0,
    )

    signal = strategy.analyze(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=candles,
        source="iq_option_demo",
        analysis_at=analysis_time_for(candles),
    )

    assert signal.action is TradeAction.WAIT
    assert "too close" in signal.reasons[0]


def test_returns_wait_when_rsi_is_extreme() -> None:
    candles = create_candles([100.0 + index for index in range(29)])
    strategy = IqOptionTrendStrategy(
        minimum_adx=0.0,
        minimum_ema_atr_ratio=0.0,
    )

    signal = strategy.analyze(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=candles,
        source="iq_option_demo",
        analysis_at=analysis_time_for(candles),
    )

    assert signal.action is TradeAction.WAIT
    assert "RSI 14 is 100.00" in signal.reasons[0]


def test_returns_wait_when_closed_candles_are_insufficient() -> None:
    candles = create_candles([100.0 + index for index in range(28)])

    signal = IqOptionTrendStrategy().analyze(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=candles,
        source="iq_option_demo",
        analysis_at=analysis_time_for(candles),
    )

    assert signal.action is TradeAction.WAIT
    assert "need at least 29 closed candles" in signal.reasons[0]
    assert signal.ema_fast is None
    assert signal.adx is None


def test_returns_wait_when_latest_candle_is_stale() -> None:
    candles = create_candles([100.0 + index for index in range(29)])

    signal = create_permissive_strategy().analyze(
        symbol="EURUSD-OTC",
        timeframe="1m",
        candles=candles,
        source="iq_option_demo",
        analysis_at=candles[-1].timestamp + timedelta(minutes=3, seconds=1),
    )

    assert signal.action is TradeAction.WAIT
    assert "old" in signal.reasons[0]