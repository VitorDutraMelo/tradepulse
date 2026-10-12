from datetime import UTC, datetime, timedelta

import pytest

from app.domain.candle import Candle
from app.providers.mock_market_data_provider import MockMarketDataProvider


def make_candle(timestamp: datetime, close: float) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=close - 1.0,
        high=close + 1.0,
        low=close - 2.0,
        close=close,
        volume=1000.0,
    )


def test_returns_candles_for_a_configured_request() -> None:
    initial_timestamp = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
    candles = (
        make_candle(initial_timestamp, 100.0),
        make_candle(initial_timestamp + timedelta(hours=1), 101.0),
        make_candle(initial_timestamp + timedelta(hours=2), 102.0),
    )
    provider = MockMarketDataProvider({("BTC-USD", "1h"): candles})

    result = provider.get_candles(
        symbol="BTC-USD",
        timeframe="1h",
        limit=2,
    )

    assert result == candles[-2:]
    assert isinstance(result, tuple)


def test_raises_an_error_when_a_request_is_not_configured() -> None:
    provider = MockMarketDataProvider({})

    with pytest.raises(
        LookupError,
        match="No mock candles configured for symbol 'ETH-USD' and timeframe '1h'",
    ):
        provider.get_candles(
            symbol="ETH-USD",
            timeframe="1h",
            limit=10,
        )


@pytest.mark.parametrize(
    ("symbol", "timeframe", "limit", "message"),
    [
        ("", "1h", 10, "symbol cannot be empty"),
        ("BTC-USD", "", 10, "timeframe cannot be empty"),
        ("BTC-USD", "1h", 0, "limit must be greater than zero"),
    ],
)
def test_rejects_invalid_requests(
    symbol: str,
    timeframe: str,
    limit: int,
    message: str,
) -> None:
    provider = MockMarketDataProvider({})

    with pytest.raises(ValueError, match=message):
        provider.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )


def test_rejects_candles_out_of_chronological_order() -> None:
    initial_timestamp = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
    newer_candle = make_candle(initial_timestamp + timedelta(hours=1), 101.0)
    older_candle = make_candle(initial_timestamp, 100.0)
    provider = MockMarketDataProvider(
        {("BTC-USD", "1h"): (newer_candle, older_candle)}
    )

    with pytest.raises(
        ValueError,
        match="candles must be returned in strictly chronological order",
    ):
        provider.get_candles(
            symbol="BTC-USD",
            timeframe="1h",
            limit=10,
        )