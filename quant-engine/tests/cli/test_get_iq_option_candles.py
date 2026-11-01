import json
from datetime import UTC, datetime

from app.cli.get_iq_option_candles import get_iq_option_candles, main
from app.domain.candle import Candle


class FakeIqOptionProvider:
    source = "otcharts_iq_option"
    venue = "iq"

    def get_symbols(self) -> tuple[str, ...]:
        return ("EURUSD-OTC",)

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        assert symbol == "EURUSD-OTC"
        assert timeframe == "1m"
        assert limit == 2

        return (
            Candle(
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                open=1.1,
                high=1.2,
                low=1.0,
                close=1.15,
                volume=18.4,
            ),
        )


def test_returns_json_safe_iq_option_candle_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.cli.get_iq_option_candles.OtchartsIqOptionMarketDataProvider",
        FakeIqOptionProvider,
    )

    payload = get_iq_option_candles("eurusd-otc", "1m", limit=2)

    assert payload == {
        "symbol": "EURUSD-OTC",
        "timeframe": "1m",
        "source": "otcharts_iq_option",
        "venue": "iq",
        "candles": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "open": 1.1,
                "high": 1.2,
                "low": 1.0,
                "close": 1.15,
                "volume": 18.4,
            },
        ],
    }


def test_rejects_symbol_not_in_official_catalogue(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.cli.get_iq_option_candles.OtchartsIqOptionMarketDataProvider",
        FakeIqOptionProvider,
    )

    exit_code = main(["--symbol", "BTCUSD-OTC", "--timeframe", "1m"])

    assert exit_code == 1


def test_writes_market_data_not_found_error_to_stderr(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "app.cli.get_iq_option_candles.OtchartsIqOptionMarketDataProvider",
        FakeIqOptionProvider,
    )

    exit_code = main(["--symbol", "BTCUSD-OTC", "--timeframe", "1m"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "MARKET_DATA_NOT_FOUND",
            "message": (
                "symbol 'BTCUSD-OTC' is not listed in the OTCharts IQ Option catalogue"
            ),
        },
    }