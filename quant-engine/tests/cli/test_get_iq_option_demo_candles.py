import json
from datetime import UTC, datetime

import pytest

from app.cli import get_iq_option_demo_candles
from app.domain.candle import Candle


class FakeIqOptionMarketDataProvider:
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


def create_candle() -> Candle:
    return Candle(
        timestamp=datetime(2026, 11, 12, 16, 20, tzinfo=UTC),
        open=1.0810,
        high=1.0815,
        low=1.0805,
        close=1.0812,
        volume=0,
    )


def test_converts_closed_candle_to_chart_payload() -> None:
    assert get_iq_option_demo_candles.candle_to_payload(
        create_candle(),
    ) == {
        "timestamp": "2026-11-12T16:20:00+00:00",
        "open": 1.0810,
        "high": 1.0815,
        "low": 1.0805,
        "close": 1.0812,
        "volume": 0,
        "closed": True,
    }


def test_returns_real_iq_option_practice_candles_for_a_supported_asset() -> None:
    provider = FakeIqOptionMarketDataProvider((create_candle(),))

    payload = get_iq_option_demo_candles.get_iq_option_demo_candles(
        symbol="GBP/USD-OTC",
        timeframe="1m",
        limit=100,
        provider=provider,
    )

    assert payload["symbol"] == "GBPUSD-OTC"
    assert payload["timeframe"] == "1m"
    assert payload["source"] == "iq_option_demo"
    assert payload["venue"] == "iq"
    assert payload["accountMode"] == "PRACTICE"
    assert payload["candles"] == [
        {
            "timestamp": "2026-11-12T16:20:00+00:00",
            "open": 1.0810,
            "high": 1.0815,
            "low": 1.0805,
            "close": 1.0812,
            "volume": 0,
            "closed": True,
        }
    ]
    assert provider.requests == [("GBPUSD-OTC", "1m", 100)]


def test_rejects_a_supported_asset_when_iq_option_returns_no_closed_candles() -> None:
    provider = FakeIqOptionMarketDataProvider(())

    with pytest.raises(
        LookupError,
        match="IQ Option returned no closed candles for GBPUSD-OTC",
    ):
        get_iq_option_demo_candles.get_iq_option_demo_candles(
            symbol="GBPUSD-OTC",
            timeframe="1m",
            limit=100,
            provider=provider,
        )


def test_rejects_an_asset_outside_the_otc_allowlist() -> None:
    provider = FakeIqOptionMarketDataProvider((create_candle(),))

    with pytest.raises(ValueError, match="unsupported IQ Option OTC symbol"):
        get_iq_option_demo_candles.get_iq_option_demo_candles(
            symbol="BTC-USD",
            timeframe="1m",
            limit=100,
            provider=provider,
        )


def test_writes_candles_json_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_payload = {
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "symbol": "EURUSD-OTC",
        "timeframe": "1m",
        "candles": [],
    }

    monkeypatch.setattr(
        get_iq_option_demo_candles,
        "get_iq_option_demo_candles",
        lambda symbol, timeframe, limit: expected_payload,
    )

    exit_code = get_iq_option_demo_candles.main(
        [
            "--symbol",
            "EURUSD-OTC",
            "--timeframe",
            "1m",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


def test_writes_iq_option_error_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def failing_get_iq_option_demo_candles(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        del symbol
        del timeframe
        del limit
        raise PermissionError("IQ Option demo authentication failed")

    monkeypatch.setattr(
        get_iq_option_demo_candles,
        "get_iq_option_demo_candles",
        failing_get_iq_option_demo_candles,
    )

    exit_code = get_iq_option_demo_candles.main(
        [
            "--symbol",
            "EURUSD-OTC",
            "--timeframe",
            "1m",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "IQ_OPTION_ACCESS_DENIED",
            "message": "IQ Option demo authentication failed",
        },
    }