from datetime import UTC, datetime, timedelta

import pytest

from app.domain.candle import Candle
from app.domain.signal import SignalDirection
from app.providers.mock_market_data_provider import MockMarketDataProvider
from app.signals.market_analysis_service import MarketAnalysisService
from app.strategies.ema_crossover_strategy import EmaCrossoverStrategy


def create_candles(close_prices: list[float]) -> list[Candle]:
    start = datetime(2026, 1, 1, tzinfo=UTC)

    return [
        Candle(
            timestamp=start + timedelta(hours=index),
            open=close,
            high=close + 1,
            low=close - 1,
            close=close,
            volume=100.0,
        )
        for index, close in enumerate(close_prices)
    ]


def create_service(candles: list[Candle]) -> MarketAnalysisService:
    provider = MockMarketDataProvider(
        {
            ("BTC-USD", "1h"): candles,
        },
    )
    strategy = EmaCrossoverStrategy(fast_period=2, slow_period=3)

    return MarketAnalysisService(provider=provider, strategy=strategy)


def test_returns_signal_from_provider_candles() -> None:
    service = create_service(create_candles([11.0, 10.0, 8.0, 7.0, 12.0]))

    signal = service.analyze("BTC-USD", "1h", limit=4)

    assert signal.direction is SignalDirection.LONG
    assert signal.score == 70
    assert signal.timestamp == datetime(2026, 1, 1, 4, tzinfo=UTC)


def test_returns_neutral_signal_when_provider_returns_insufficient_candles() -> None:
    service = create_service(create_candles([10.0, 8.0, 7.0]))

    signal = service.analyze("BTC-USD", "1h", limit=3)

    assert signal.direction is SignalDirection.NEUTRAL
    assert signal.score == 0
    assert "Insufficient data" in signal.reasons[0]


def test_propagates_error_when_provider_has_no_requested_market_data() -> None:
    service = create_service(create_candles([10.0, 8.0, 7.0, 12.0]))

    with pytest.raises(LookupError):
        service.analyze("ETH-USD", "1h", limit=4)