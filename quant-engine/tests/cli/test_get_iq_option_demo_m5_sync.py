import json
from datetime import UTC, datetime

import pytest

from app.cli import get_iq_option_demo_m5_sync
from app.domain.candle import Candle


class FakeIqOptionMarketDataProvider:
    source = "iq_option_demo"
    venue = "iq"

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


def candle(open_time: datetime) -> Candle:
    return Candle(
        timestamp=open_time,
        open=1.25,
        high=1.251,
        low=1.249,
        close=1.2505,
        volume=0,
    )


def fixed_clock(*values: datetime):
    iterator = iter(values)

    return lambda: next(iterator)


def test_returns_updated_when_the_latest_m5_close_is_available() -> None:
    provider = FakeIqOptionMarketDataProvider(
        (candle(datetime(2026, 11, 14, 12, 5, tzinfo=UTC)),)
    )
    clock = fixed_clock(
        datetime(2026, 11, 14, 12, 10, 2, tzinfo=UTC),
        datetime(2026, 11, 14, 12, 10, 2, tzinfo=UTC),
        datetime(2026, 11, 14, 12, 10, 2, 500000, tzinfo=UTC),
        datetime(2026, 11, 14, 12, 10, 2, 501000, tzinfo=UTC),
    )

    payload = get_iq_option_demo_m5_sync.get_iq_option_demo_m5_sync(
        symbol="GBP/USD-OTC",
        provider=provider,
        now=clock,
    )

    assert payload["state"] == "UPDATED"
    assert payload["timeframe"] == "5m"
    assert payload["expectedLatestCloseTime"] == "2026-11-14T12:10:00+00:00"
    assert payload["latestClosedCandle"]["closeTime"] == (
        "2026-11-14T12:10:00+00:00"
    )
    assert payload["timing"]["iqCandleAvailabilityAt"] is None
    assert provider.requests == [("GBPUSD-OTC", "5m", 3)]


@pytest.mark.parametrize(
    ("latest_open_time", "expected_state"),
    [
        (datetime(2026, 11, 14, 12, 0, tzinfo=UTC), "AWAITING_CONFIRMATION"),
        (datetime(2026, 11, 14, 11, 55, tzinfo=UTC), "STALE"),
    ],
)
def test_classifies_lag_without_using_an_arbitrary_delay(
    latest_open_time: datetime,
    expected_state: str,
) -> None:
    provider = FakeIqOptionMarketDataProvider((candle(latest_open_time),))
    clock = fixed_clock(
        datetime(2026, 11, 14, 12, 10, 2, tzinfo=UTC),
        datetime(2026, 11, 14, 12, 10, 2, tzinfo=UTC),
        datetime(2026, 11, 14, 12, 10, 2, tzinfo=UTC),
        datetime(2026, 11, 14, 12, 10, 2, tzinfo=UTC),
    )

    payload = get_iq_option_demo_m5_sync.get_iq_option_demo_m5_sync(
        symbol="GBPUSD-OTC",
        provider=provider,
        now=clock,
    )

    assert payload["state"] == expected_state


def test_rejects_assets_other_than_the_first_delivery_symbol() -> None:
    with pytest.raises(ValueError, match="only GBPUSD-OTC"):
        get_iq_option_demo_m5_sync.get_iq_option_demo_m5_sync(
            symbol="EURUSD-OTC",
            provider=FakeIqOptionMarketDataProvider(()),
        )


def test_writes_provider_error_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def failing_sync(symbol: str) -> dict[str, object]:
        del symbol
        raise ConnectionError("could not connect to IQ Option")

    monkeypatch.setattr(
        get_iq_option_demo_m5_sync,
        "get_iq_option_demo_m5_sync",
        failing_sync,
    )

    exit_code = get_iq_option_demo_m5_sync.main(["--symbol", "GBPUSD-OTC"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "IQ_OPTION_UNAVAILABLE",
            "message": "could not connect to IQ Option",
        },
    }