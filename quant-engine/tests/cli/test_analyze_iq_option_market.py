import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.cli import analyze_iq_option_market
from app.domain.candle import Candle
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


def create_candles() -> tuple[Candle, ...]:
    candles: list[Candle] = []

    for minute in range(22):
        price = 1.1000 + minute * 0.0001
        candles.append(
            Candle(
                timestamp=datetime(
                    2026,
                    11,
                    7,
                    11,
                    minute,
                    tzinfo=UTC,
                ),
                open=price,
                high=price + 0.0001,
                low=price - 0.0001,
                close=price,
                volume=0.0,
            )
        )

    return tuple(candles)


class FakeIqOptionProvider:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles
        self.requests: list[tuple[str, str, int]] = []

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        self.requests.append((symbol, timeframe, limit))
        return self._candles


class FakeAnalysisRepository:
    def __init__(self) -> None:
        self.saved_signal: Signal | None = None
        self.saved_candles: tuple[Candle, ...] | None = None
        self.recorded_at: datetime | None = None

    def save(
        self,
        signal: Signal,
        candles: tuple[Candle, ...],
        recorded_at: datetime,
    ) -> Path:
        self.saved_signal = signal
        self.saved_candles = candles
        self.recorded_at = recorded_at

        return Path("data/iq-option-demo-analyses/iq-demo-test-record.json")


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


def test_persists_the_signal_and_closed_candles_used_for_analysis() -> None:
    candles = create_candles()
    provider = FakeIqOptionProvider(candles)
    repository = FakeAnalysisRepository()
    recorded_at = datetime(2026, 11, 7, 12, 1, tzinfo=UTC)

    payload = analyze_iq_option_market.analyze_iq_option_market(
        symbol="EURUSD-OTC",
        timeframe="1m",
        limit=30,
        provider=provider,
        analysis_repository=repository,
        now=lambda: recorded_at,
    )

    assert provider.requests == [("EURUSD-OTC", "1m", 30)]
    assert repository.saved_signal is not None
    assert repository.saved_signal.symbol == "EURUSD-OTC"
    assert repository.saved_candles == candles
    assert repository.recorded_at == recorded_at
    assert payload["recordId"] == "iq-demo-test-record"


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