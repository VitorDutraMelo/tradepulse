from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from app.providers.iq_option_market_data_provider import (
    IqOptionClient,
    IqOptionMarketDataProvider,
)


class FakeIqOptionClient:
    def __init__(
        self,
        connected: bool = True,
        reason: str | None = None,
        open_times: object | None = None,
        candles: object | None = None,
    ) -> None:
        self.connected = connected
        self.reason = reason
        self.open_times = open_times or {}
        self.candles = candles or []
        self.balance_types: list[str] = []
        self.candle_requests: list[tuple[str, int, int, int]] = []

    def connect(self) -> tuple[bool, str | None]:
        return self.connected, self.reason

    def change_balance(self, balance_type: str) -> object:
        self.balance_types.append(balance_type)
        return True

    def get_all_open_time(self) -> object:
        return self.open_times

    def get_candles(
        self,
        active: str,
        interval_seconds: int,
        count: int,
        end_time: int,
    ) -> object:
        self.candle_requests.append(
            (
                active,
                interval_seconds,
                count,
                end_time,
            )
        )
        return self.candles


def create_provider(
    client: FakeIqOptionClient,
    now: datetime,
) -> IqOptionMarketDataProvider:
    return IqOptionMarketDataProvider(
        email="demo@example.com",
        password="demo-password",
        now=lambda: now,
        client_factory=lambda _, __: cast(IqOptionClient, client),
    )


def test_lists_only_currently_open_iq_option_symbols() -> None:
    client = FakeIqOptionClient(
        open_times={
            "binary": {
                "EURUSD": {"open": True},
                "GBPUSD": {"open": False},
            },
            "digital": {
                "EURUSD-OTC": {"open": True},
            },
        }
    )
    provider = create_provider(
        client,
        datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
    )

    symbols = provider.get_symbols()

    assert symbols == ("EURUSD", "EURUSD-OTC")
    assert client.balance_types == ["PRACTICE"]


def test_returns_only_closed_normalized_iq_option_candles() -> None:
    first_open = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    second_open = first_open + timedelta(minutes=1)
    third_open = second_open + timedelta(minutes=1)
    current_time = third_open + timedelta(seconds=30)

    client = FakeIqOptionClient(
        candles=[
            {
                "from": int(second_open.timestamp()),
                "to": int(third_open.timestamp()),
                "open": 1.1020,
                "max": 1.1030,
                "min": 1.1010,
                "close": 1.1025,
                "volume": 12,
            },
            {
                "from": int(first_open.timestamp()),
                "to": int(second_open.timestamp()),
                "open": 1.1000,
                "max": 1.1020,
                "min": 1.0990,
                "close": 1.1010,
                "volume": 10,
            },
            {
                "from": int(third_open.timestamp()),
                "to": int((third_open + timedelta(minutes=1)).timestamp()),
                "open": 1.1025,
                "max": 1.1040,
                "min": 1.1020,
                "close": 1.1030,
                "volume": 8,
            },
        ]
    )
    provider = create_provider(client, current_time)

    candles = provider.get_candles(
        symbol="EUR/USD",
        timeframe="1m",
        limit=3,
    )

    assert [candle.timestamp for candle in candles] == [
        first_open,
        second_open,
    ]
    assert candles[0].open == 1.1000
    assert candles[1].close == 1.1025
    assert client.candle_requests == [
        (
            "EURUSD",
            60,
            3,
            int(current_time.timestamp()),
        )
    ]
    assert client.balance_types == ["PRACTICE"]


def test_rejects_unsupported_timeframes_and_limits() -> None:
    client = FakeIqOptionClient()
    provider = create_provider(
        client,
        datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="unsupported IQ Option timeframe"):
        provider.get_candles(
            symbol="EURUSD",
            timeframe="30m",
            limit=10,
        )

    with pytest.raises(ValueError, match="must not exceed 1000"):
        provider.get_candles(
            symbol="EURUSD",
            timeframe="1m",
            limit=1001,
        )


def test_rejects_failed_iq_option_authentication() -> None:
    client = FakeIqOptionClient(
        connected=False,
        reason="invalid credentials",
    )
    provider = create_provider(
        client,
        datetime(2026, 11, 7, 12, 0, tzinfo=UTC),
    )

    with pytest.raises(
        PermissionError,
        match="IQ Option demo authentication failed: invalid credentials",
    ):
        provider.get_symbols()

    assert client.balance_types == []


def test_rejects_invalid_candle_payloads() -> None:
    open_timestamp = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
    close_timestamp = open_timestamp + timedelta(minutes=1)

    client = FakeIqOptionClient(
        candles=[
            {
                "from": int(open_timestamp.timestamp()),
                "to": int(close_timestamp.timestamp()),
                "open": 1.1000,
                "max": 1.0990,
                "min": 1.0980,
                "close": 1.1010,
                "volume": 10,
            }
        ]
    )
    provider = create_provider(
        client,
        datetime(2026, 11, 7, 12, 2, tzinfo=UTC),
    )

    with pytest.raises(
        ValueError,
        match="high must be greater than or equal to open and close",
    ):
        provider.get_candles(
            symbol="EURUSD",
            timeframe="1m",
            limit=1,
        )