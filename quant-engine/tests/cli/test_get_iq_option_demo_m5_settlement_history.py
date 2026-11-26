from datetime import UTC, datetime

from app.cli.get_iq_option_demo_m5_signal_with_m15 import (
    get_closed_m5_settlement_candles,
)
from app.domain.candle import Candle


class StubProvider:
    def __init__(self, candles: tuple[Candle, ...]) -> None:
        self._candles = candles
        self.calls: list[tuple[str, str, int]] = []

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        self.calls.append((symbol, timeframe, limit))
        return self._candles


def create_candle(
    hour: int,
    minute: int,
) -> Candle:
    return Candle(
        timestamp=datetime(
            2026,
            11,
            21,
            hour,
            minute,
            tzinfo=UTC,
        ),
        open=1.3000,
        high=1.3010,
        low=1.2990,
        close=1.3005,
        volume=0.0,
    )


def test_returns_only_effectively_closed_m5_candles() -> None:
    provider = StubProvider(
        (
            create_candle(15, 50),
            create_candle(15, 55),
            create_candle(16, 0),
        )
    )

    candles = get_closed_m5_settlement_candles(
        symbol="GBPUSD-OTC",
        provider=provider,
        observed_at=datetime(
            2026,
            11,
            21,
            16,
            3,
            tzinfo=UTC,
        ),
    )

    assert [candle.timestamp.minute for candle in candles] == [50, 55]
    assert provider.calls == [
        ("GBPUSD-OTC", "5m", 260),
    ]


def test_includes_the_settlement_candle_after_it_has_closed() -> None:
    provider = StubProvider(
        (
            create_candle(15, 55),
            create_candle(16, 0),
        )
    )

    candles = get_closed_m5_settlement_candles(
        symbol="GBPUSD-OTC",
        provider=provider,
        observed_at=datetime(
            2026,
            11,
            21,
            16,
            5,
            tzinfo=UTC,
        ),
    )

    assert [candle.timestamp.minute for candle in candles] == [55, 0]


def test_rejects_an_invalid_settlement_history_limit() -> None:
    provider = StubProvider(())

    try:
        get_closed_m5_settlement_candles(
            symbol="GBPUSD-OTC",
            provider=provider,
            observed_at=datetime(
                2026,
                11,
                21,
                16,
                5,
                tzinfo=UTC,
            ),
            limit=0,
        )
    except ValueError as error:
        assert "must be positive" in str(error)
    else:
        raise AssertionError("Expected an invalid history limit to fail")
