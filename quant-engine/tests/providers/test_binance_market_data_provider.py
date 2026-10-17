import json
from datetime import UTC, datetime
from urllib.error import URLError

import pytest

from app.providers.binance_market_data_provider import BinanceMarketDataProvider


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None


def test_fetches_and_converts_closed_binance_candles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = ""

    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        nonlocal requested_url
        requested_url = url

        return FakeResponse(
            [
                [
                    1767225600000,
                    "100.0",
                    "110.0",
                    "90.0",
                    "105.0",
                    "15.5",
                    1767229199999,
                ],
                [
                    1767229200000,
                    "105.0",
                    "115.0",
                    "95.0",
                    "110.0",
                    "20.0",
                    1767232799999,
                ],
            ],
        )

    monkeypatch.setattr(
        "app.providers.binance_market_data_provider.urlopen",
        fake_urlopen,
    )
    provider = BinanceMarketDataProvider()

    candles = provider.get_candles("BTC-USD", "1h", limit=2)

    assert "symbol=BTCUSDT" in requested_url
    assert "interval=1h" in requested_url
    assert "limit=2" in requested_url
    assert len(candles) == 2
    assert candles[0].timestamp == datetime(2026, 1, 1, tzinfo=UTC)
    assert candles[0].open == 100.0
    assert candles[0].high == 110.0
    assert candles[0].low == 90.0
    assert candles[0].close == 105.0
    assert candles[0].volume == 15.5


def test_ignores_unclosed_binance_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        return FakeResponse(
            [
                [
                    1767225600000,
                    "100.0",
                    "110.0",
                    "90.0",
                    "105.0",
                    "15.5",
                    1767229199999,
                ],
                [
                    1893456000000,
                    "105.0",
                    "115.0",
                    "95.0",
                    "110.0",
                    "20.0",
                    1893459599999,
                ],
            ],
        )

    monkeypatch.setattr(
        "app.providers.binance_market_data_provider.urlopen",
        fake_urlopen,
    )
    provider = BinanceMarketDataProvider()

    candles = provider.get_candles("BTC-USD", "1h", limit=2)

    assert len(candles) == 1
    assert candles[0].close == 105.0


def test_rejects_limit_above_binance_maximum() -> None:
    provider = BinanceMarketDataProvider()

    with pytest.raises(ValueError, match="limit must not exceed 1000 for Binance"):
        provider.get_candles("BTC-USD", "1h", limit=1001)


def test_converts_network_failure_to_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        raise URLError("offline")

    monkeypatch.setattr(
        "app.providers.binance_market_data_provider.urlopen",
        fake_urlopen,
    )
    provider = BinanceMarketDataProvider()

    with pytest.raises(
        ConnectionError,
        match="could not retrieve candles from Binance",
    ):
        provider.get_candles("BTC-USD", "1h", limit=2)


def test_rejects_invalid_binance_candle(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(url: str, timeout: float) -> FakeResponse:
        return FakeResponse([["invalid"]])

    monkeypatch.setattr(
        "app.providers.binance_market_data_provider.urlopen",
        fake_urlopen,
    )
    provider = BinanceMarketDataProvider()

    with pytest.raises(ValueError, match="Binance returned an invalid candle"):
        provider.get_candles("BTC-USD", "1h", limit=1)


def test_keeps_usdt_symbol_unchanged() -> None:
    assert BinanceMarketDataProvider._to_binance_symbol("BTC-USDT") == "BTCUSDT"