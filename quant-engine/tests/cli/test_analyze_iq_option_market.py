import json
from datetime import UTC, datetime

import pytest

from app.cli import analyze_iq_option_market
from app.domain.signal import Signal, SignalDirection


def create_signal() -> Signal:
    return Signal(
        symbol="EURUSD",
        timeframe="1m",
        timestamp=datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
        direction=SignalDirection.LONG,
        score=70,
        reasons=("EMA 9 crossed above EMA 21",),
    )


def test_converts_iq_option_signal_to_explicit_json_payload() -> None:
    payload = analyze_iq_option_market.signal_to_payload(create_signal())

    assert payload == {
        "symbol": "EURUSD",
        "timeframe": "1m",
        "timestamp": "2026-11-07T12:00:00+00:00",
        "direction": "LONG",
        "score": 70,
        "reasons": ["EMA 9 crossed above EMA 21"],
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "strategy": "ema_crossover",
        "indicators": {
            "fastEmaPeriod": 9,
            "slowEmaPeriod": 21,
        },
        "disclaimer": (
            "Technical analysis only. LONG, SHORT and NEUTRAL are not "
            "automatic CALL, PUT or WAIT instructions."
        ),
    }


def test_writes_iq_option_analysis_json_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_payload = analyze_iq_option_market.signal_to_payload(
        create_signal()
    )

    def fake_analyze_iq_option_market(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        assert symbol == "EURUSD"
        assert timeframe == "1m"
        assert limit == 100
        return expected_payload

    monkeypatch.setattr(
        analyze_iq_option_market,
        "analyze_iq_option_market",
        fake_analyze_iq_option_market,
    )

    exit_code = analyze_iq_option_market.main(
        [
            "--symbol",
            "EURUSD",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


def test_lists_iq_option_symbols_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_payload = {
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "symbols": ["EURUSD", "EURUSD-OTC"],
    }

    monkeypatch.setattr(
        analyze_iq_option_market,
        "list_iq_option_symbols",
        lambda: expected_payload,
    )

    exit_code = analyze_iq_option_market.main(["--list-symbols"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


def test_writes_iq_option_access_error_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def failing_analyze_iq_option_market(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> dict[str, object]:
        del symbol
        del timeframe
        del limit
        raise PermissionError("IQ Option demo authentication failed")

    monkeypatch.setattr(
        analyze_iq_option_market,
        "analyze_iq_option_market",
        failing_analyze_iq_option_market,
    )

    exit_code = analyze_iq_option_market.main(
        [
            "--symbol",
            "EURUSD",
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