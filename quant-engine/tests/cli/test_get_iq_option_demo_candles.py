import json
from datetime import UTC, datetime

import pytest

from app.cli import get_iq_option_demo_candles
from app.domain.candle import Candle


class FakeIqOptionMarketDataProvider:
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
        timestamp=datetime(2026, 11, 7, 1, 3, tzinfo=UTC),
        open=1.0810,
        high=1.0815,
        low=1.0805,
        close=1.0812,
        volume=0,
    )


def test_converts_closed_candle_to_comparison_payload() -> None:
    payload = get_iq_option_demo_candles.candle_to_payload(
        candle=create_candle(),
        timeframe="1m",
    )

    assert payload == {
        "openTimestamp": "2026-11-07T01:03:00+00:00",
        "closeTimestamp": "2026-11-07T01:04:00+00:00",
        "open": 1.0810,
        "high": 1.0815,
        "low": 1.0805,
        "close": 1.0812,
        "volume": 0,
        "closed": True,
    }


def test_returns_normalized_iq_option_demo_candles() -> None:
    provider = FakeIqOptionMarketDataProvider((create_candle(),))

    payload = get_iq_option_demo_candles.get_iq_option_demo_candles(
        symbol="EUR/USD-OTC",
        timeframe="1m",
        limit=5,
        provider=provider,
    )

    assert payload["symbol"] == "EURUSD-OTC"
    assert payload["timeframe"] == "1m"
    assert payload["source"] == "iq_option_demo"
    assert payload["venue"] == "iq"
    assert payload["accountMode"] == "PRACTICE"
    assert payload["candles"] == [
        {
            "openTimestamp": "2026-11-07T01:03:00+00:00",
            "closeTimestamp": "2026-11-07T01:04:00+00:00",
            "open": 1.0810,
            "high": 1.0815,
            "low": 1.0805,
            "close": 1.0812,
            "volume": 0,
            "closed": True,
        }
    ]
    assert provider.requests == [("EURUSD-OTC", "1m", 5)]


def test_writes_candles_json_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_payload = {
        "symbol": "EURUSD",
        "timeframe": "1m",
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
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
            "EURUSD",
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
            "EURUSD",
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