import json
from datetime import UTC, datetime

from app.cli.analyze_market import main, signal_to_payload
from app.domain.signal import Signal, SignalDirection


def create_signal() -> Signal:
    return Signal(
        symbol="BTC-USDT",
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        direction=SignalDirection.LONG,
        score=70,
        reasons=("EMA 9 crossed above EMA 21",),
    )


def test_converts_signal_to_json_safe_payload() -> None:
    payload = signal_to_payload(create_signal())

    assert payload == {
        "symbol": "BTC-USDT",
        "timeframe": "1h",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "direction": "LONG",
        "score": 70,
        "reasons": ["EMA 9 crossed above EMA 21"],
        "source": "binance_spot",
        "strategy": "ema_crossover",
        "indicators": {
            "fastEmaPeriod": 9,
            "slowEmaPeriod": 21,
        },
    }


def test_writes_analysis_json_to_stdout(
    monkeypatch,
    capsys,
) -> None:
    expected_payload = signal_to_payload(create_signal())

    def fake_analyze_market(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        assert symbol == "BTC-USDT"
        assert timeframe == "1h"
        assert limit == 100

        return expected_payload

    monkeypatch.setattr(
        "app.cli.analyze_market.analyze_market",
        fake_analyze_market,
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
    def fake_analyze_market(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        raise ConnectionError("could not retrieve candles from Binance")

    monkeypatch.setattr(
        "app.cli.analyze_market.analyze_market",
        fake_analyze_market,
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