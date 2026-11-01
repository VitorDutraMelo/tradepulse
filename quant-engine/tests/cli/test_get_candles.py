import json
from datetime import UTC, datetime

from app.cli.get_candles import candle_to_payload, main
from app.domain.candle import Candle


def create_candle() -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        open=100.0,
        high=110.0,
        low=90.0,
        close=105.0,
        volume=15.5,
    )


def test_converts_candle_to_json_safe_payload() -> None:
    payload = candle_to_payload(create_candle())

    assert payload == {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "open": 100.0,
        "high": 110.0,
        "low": 90.0,
        "close": 105.0,
        "volume": 15.5,
    }


def test_writes_candles_json_to_stdout(
    monkeypatch,
    capsys,
) -> None:
    expected_payload = {
        "symbol": "BTC-USDT",
        "timeframe": "1h",
        "source": "binance_spot",
        "candles": [candle_to_payload(create_candle())],
    }

    def fake_get_market_candles(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        assert symbol == "BTC-USDT"
        assert timeframe == "1h"
        assert limit == 100

        return expected_payload

    monkeypatch.setattr(
        "app.cli.get_candles.get_market_candles",
        fake_get_market_candles,
    )

    exit_code = main(["--symbol", "BTC-USDT", "--timeframe", "1h"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


def test_writes_error_json_to_stderr(
    monkeypatch,
    capsys,
) -> None:
    def fake_get_market_candles(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        raise ConnectionError("could not retrieve candles from Binance")

    monkeypatch.setattr(
        "app.cli.get_candles.get_market_candles",
        fake_get_market_candles,
    )

    exit_code = main(["--symbol", "BTC-USDT", "--timeframe", "1h"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "MARKET_DATA_UNAVAILABLE",
            "message": "could not retrieve candles from Binance",
        },
    }