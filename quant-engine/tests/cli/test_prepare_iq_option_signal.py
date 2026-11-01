import json
from datetime import UTC, datetime

from app.cli.prepare_iq_option_signal import main, trade_signal_to_payload
from app.domain.signal import SignalDirection
from app.domain.trade_signal import (
    MarketCategory,
    SignalPlatform,
    TradeAction,
    TradeSignal,
)


def create_trade_signal() -> TradeSignal:
    return TradeSignal(
        platform=SignalPlatform.IQ_OPTION,
        asset="BTC-USD",
        market=MarketCategory.CRYPTO,
        timeframe="1h",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        data_source="binance_spot",
        analysis_direction=SignalDirection.LONG,
        action=TradeAction.WAIT,
        entry_time=None,
        expiration_time=None,
        reasons=(
            "EMA 9 crossed above EMA 21",
            "No IQ Option policy is configured for this market and data source; "
            "manual action remains WAIT.",
        ),
    )


def test_converts_trade_signal_to_json_safe_payload() -> None:
    payload = trade_signal_to_payload(create_trade_signal())

    assert payload == {
        "platform": "IQ_OPTION",
        "asset": "BTC-USD",
        "market": "CRYPTO",
        "timeframe": "1h",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "dataSource": "binance_spot",
        "analysisDirection": "LONG",
        "action": "WAIT",
        "entryTime": None,
        "expirationTime": None,
        "reasons": [
            "EMA 9 crossed above EMA 21",
            (
                "No IQ Option policy is configured for this market and data "
                "source; manual action remains WAIT."
            ),
        ],
    }


def test_writes_iq_option_signal_json_to_stdout(
    monkeypatch,
    capsys,
) -> None:
    expected_payload = trade_signal_to_payload(create_trade_signal())

    def fake_prepare_iq_option_signal(
        symbol: str,
        timeframe: str,
        limit: int,
        market: MarketCategory,
    ) -> dict[str, object]:
        assert symbol == "BTC-USD"
        assert timeframe == "1h"
        assert limit == 100
        assert market is MarketCategory.CRYPTO

        return expected_payload

    monkeypatch.setattr(
        "app.cli.prepare_iq_option_signal.prepare_iq_option_signal",
        fake_prepare_iq_option_signal,
    )

    exit_code = main(["--symbol", "BTC-USD", "--timeframe", "1h"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


def test_writes_error_json_to_stderr(
    monkeypatch,
    capsys,
) -> None:
    def fake_prepare_iq_option_signal(
        symbol: str,
        timeframe: str,
        limit: int,
        market: MarketCategory,
    ) -> dict[str, object]:
        raise ConnectionError("could not retrieve candles from Binance")

    monkeypatch.setattr(
        "app.cli.prepare_iq_option_signal.prepare_iq_option_signal",
        fake_prepare_iq_option_signal,
    )

    exit_code = main(["--symbol", "BTC-USD", "--timeframe", "1h"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "MARKET_DATA_UNAVAILABLE",
            "message": "could not retrieve candles from Binance",
        },
    }