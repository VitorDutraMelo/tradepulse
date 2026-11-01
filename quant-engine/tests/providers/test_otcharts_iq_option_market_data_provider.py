import json
from datetime import UTC, datetime
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from app.providers.otcharts_iq_option_market_data_provider import (
    OtchartsIqOptionMarketDataProvider,
)


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None


def create_provider() -> OtchartsIqOptionMarketDataProvider:
    return OtchartsIqOptionMarketDataProvider(
        api_key="test-key",
        base_url="https://otcharts.example",
    )


def test_returns_official_iq_option_symbol_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = ""
    authorization = ""
    user_agent = ""

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        nonlocal authorization, requested_url, user_agent
        requested_url = request.full_url
        authorization = request.get_header("Authorization")
        user_agent = request.get_header("User-agent")

        return FakeResponse(
            {
                "venue": "iq",
                "count": 2,
                "symbols": [
                    {"symbol": "EURUSD-OTC", "name": "EUR/USD OTC"},
                    {"symbol": "GBPUSD-OTC", "name": "GBP/USD OTC"},
                ],
            }
        )

    monkeypatch.setattr(
        "app.providers.otcharts_iq_option_market_data_provider.urlopen",
        fake_urlopen,
    )

    symbols = create_provider().get_symbols()

    assert symbols == ("EURUSD-OTC", "GBPUSD-OTC")
    assert requested_url == "https://otcharts.example/v1/symbols?venue=iq"
    assert authorization == "Bearer test-key"
    assert user_agent == "TradePulse-QuantEngine/0.1"


def test_fetches_closed_iq_option_one_minute_candles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested_url = ""

    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        nonlocal requested_url
        requested_url = request.full_url

        return FakeResponse(
            {
                "symbol": "EURUSD-OTC",
                "gaps": {"runs": 0, "missingBars": 0},
                "candles": [
                    {
                        "time": 1767225600,
                        "open": 1.1,
                        "high": 1.2,
                        "low": 1.0,
                        "close": 1.15,
                        "volume": 18.4,
                    },
                    {
                        "time": 1767225660,
                        "open": 1.15,
                        "high": 1.25,
                        "low": 1.1,
                        "close": 1.2,
                        "volume": 11.9,
                    },
                ],
            }
        )

    monkeypatch.setattr(
        "app.providers.otcharts_iq_option_market_data_provider.urlopen",
        fake_urlopen,
    )

    candles = create_provider().get_candles("EURUSD-OTC", "1m", limit=2)

    assert "venue=iq" in requested_url
    assert "symbol=EURUSD-OTC" in requested_url
    assert "tf=60" in requested_url
    assert "limit=2" in requested_url
    assert len(candles) == 2
    assert candles[0].timestamp == datetime(2026, 1, 1, tzinfo=UTC)
    assert candles[0].close == 1.15
    assert candles[0].volume == 18.4


def test_ignores_an_unclosed_iq_option_candle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(
            {
                "symbol": "EURUSD-OTC",
                "gaps": {"runs": 0, "missingBars": 0},
                "candles": [
                    {
                        "time": 1767225600,
                        "open": 1.1,
                        "high": 1.2,
                        "low": 1.0,
                        "close": 1.15,
                        "volume": 18.4,
                    },
                    {
                        "time": 4102444800,
                        "open": 1.15,
                        "high": 1.25,
                        "low": 1.1,
                        "close": 1.2,
                        "volume": 11.9,
                    },
                ],
            }
        )

    monkeypatch.setattr(
        "app.providers.otcharts_iq_option_market_data_provider.urlopen",
        fake_urlopen,
    )

    candles = create_provider().get_candles("EURUSD-OTC", "1m", limit=2)

    assert len(candles) == 1
    assert candles[0].close == 1.15


def test_rejects_candle_responses_with_gaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        return FakeResponse(
            {
                "symbol": "EURUSD-OTC",
                "gaps": {"runs": 1, "missingBars": 2},
                "candles": [],
            }
        )

    monkeypatch.setattr(
        "app.providers.otcharts_iq_option_market_data_provider.urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        ValueError,
        match="contains missing bars and cannot be used for analysis",
    ):
        create_provider().get_candles("EURUSD-OTC", "1m", limit=2)


def test_rejects_unknown_iq_option_timeframe() -> None:
    with pytest.raises(ValueError, match="timeframe '3m' is not supported"):
        create_provider().get_candles("EURUSD-OTC", "3m", limit=2)


def test_rejects_limit_above_otcharts_maximum() -> None:
    with pytest.raises(ValueError, match="limit must not exceed 5000 for OTCharts"):
        create_provider().get_candles("EURUSD-OTC", "1m", limit=5001)


def test_reports_missing_api_key() -> None:
    with pytest.raises(ValueError, match="OTCHARTS_API_KEY is not configured"):
        OtchartsIqOptionMarketDataProvider(api_key="")


def test_converts_not_found_response_to_lookup_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        raise HTTPError(request.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(
        "app.providers.otcharts_iq_option_market_data_provider.urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        LookupError,
        match="could not find the requested IQ Option data",
    ):
        create_provider().get_candles("UNKNOWN-OTC", "1m", limit=2)


def test_converts_permission_response_to_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request: Request, timeout: float) -> FakeResponse:
        raise HTTPError(request.full_url, 401, "Unauthorized", None, None)

    monkeypatch.setattr(
        "app.providers.otcharts_iq_option_market_data_provider.urlopen",
        fake_urlopen,
    )

    with pytest.raises(
        PermissionError,
        match="rejected the API key or IQ Option venue access",
    ):
        create_provider().get_candles("EURUSD-OTC", "1m", limit=2)