from datetime import UTC, datetime, timedelta

from app.cli.iq_option_demo_m15_context import (
    get_iq_option_demo_m15_context,
)
from app.domain.candle import Candle


class FakeProvider:
    source = "iq_option_demo"
    venue = "iq"

    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self.candles = candles
        self.requests: list[tuple[str, str, int]] = []

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        self.requests.append((symbol, timeframe, limit))
        return self.candles


def make_bullish_candles() -> tuple[Candle, ...]:
    start = datetime(2026, 11, 14, 0, 0, tzinfo=UTC)
    candles: list[Candle] = []

    for index in range(260):
        close = 1.3000 + (index * 0.0001)
        high = close + 0.00005
        low = close - 0.00005

        if index == 235:
            high = 1.5000
        elif index == 245:
            high = 1.6000
        elif index == 238:
            low = 1.1000
        elif index == 248:
            low = 1.2000

        candles.append(
            Candle(
                timestamp=start + timedelta(minutes=15 * index),
                open=close - 0.00002,
                high=high,
                low=low,
                close=close,
                volume=0.0,
            )
        )

    return tuple(candles)


def test_returns_confirmed_bullish_m15_context() -> None:
    candles = make_bullish_candles()
    provider = FakeProvider(candles)
    now = candles[-1].timestamp + timedelta(minutes=15)

    payload = get_iq_option_demo_m15_context(
        symbol="GBPUSD-OTC",
        provider=provider,
        now=lambda: now,
    )

    assert payload["state"] == "UPDATED"
    assert payload["trend"] == "BULLISH"
    assert payload["structure"] == "HIGHER_HIGH_HIGHER_LOW"
    assert payload["dataQuality"]["receivedClosedCandles"] == 260
    assert payload["dataQuality"]["candlesContiguous"] is True
    assert provider.requests == [("GBPUSD-OTC", "15m", 260)]


def test_returns_neutral_when_m15_data_is_stale() -> None:
    candles = make_bullish_candles()
    provider = FakeProvider(candles)
    now = candles[-1].timestamp + timedelta(minutes=45)

    payload = get_iq_option_demo_m15_context(
        symbol="GBPUSD-OTC",
        provider=provider,
        now=lambda: now,
    )

    assert payload["state"] == "STALE"
    assert payload["trend"] == "NEUTRAL"


def test_rejects_an_asset_outside_the_first_validation_scope() -> None:
    provider = FakeProvider(make_bullish_candles())

    try:
        get_iq_option_demo_m15_context(
            symbol="EURUSD-OTC",
            provider=provider,
        )
    except ValueError as error:
        assert "only GBPUSD-OTC" in str(error)
    else:
        raise AssertionError("Expected ValueError for unsupported M15 symbol.")
