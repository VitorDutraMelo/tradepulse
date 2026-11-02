from datetime import UTC, datetime

import pytest

from app.domain.market_tick import MarketTick


def test_normalizes_symbol() -> None:
    tick = MarketTick(
        symbol=" eurusd-otc ",
        timestamp=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        price=1.12345,
    )

    assert tick.symbol == "EURUSD-OTC"


@pytest.mark.parametrize(
    ("symbol", "timestamp", "price", "volume", "message"),
    [
        (
            "",
            datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
            1.12345,
            None,
            "symbol cannot be empty",
        ),
        (
            "EURUSD-OTC",
            datetime(2026, 11, 2, 10, 0),
            1.12345,
            None,
            "timestamp must be timezone-aware",
        ),
        (
            "EURUSD-OTC",
            datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
            0,
            None,
            "price must be greater than zero",
        ),
        (
            "EURUSD-OTC",
            datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
            1.12345,
            -1,
            "volume cannot be negative",
        ),
    ],
)
def test_rejects_invalid_ticks(
    symbol: str,
    timestamp: datetime,
    price: float,
    volume: float | None,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        MarketTick(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            volume=volume,
        )