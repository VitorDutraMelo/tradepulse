from datetime import UTC, datetime

import pytest

from app.domain.market_tick import MarketTick
from app.services.one_minute_candle_builder import OneMinuteCandleBuilder


def create_tick(
    minute: int,
    second: int,
    price: float,
    volume: float | None = None,
) -> MarketTick:
    return MarketTick(
        symbol="EURUSD-OTC",
        timestamp=datetime(2026, 11, 2, 10, minute, second, tzinfo=UTC),
        price=price,
        volume=volume,
    )


def test_builds_closed_one_minute_candle_after_minute_rollover() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")

    assert builder.add_tick(create_tick(0, 2, 1.1000, 2.0)) == ()
    assert builder.add_tick(create_tick(0, 15, 1.1010, 3.0)) == ()
    assert builder.add_tick(create_tick(0, 42, 1.0990, 1.5)) == ()

    result = builder.add_tick(create_tick(1, 1, 1.1005, 4.0))

    assert len(result) == 1

    collected = result[0]

    assert collected.candle.timestamp == datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
    assert collected.candle.open == 1.1000
    assert collected.candle.high == 1.1010
    assert collected.candle.low == 1.0990
    assert collected.candle.close == 1.0990
    assert collected.candle.volume == 6.5
    assert collected.tick_count == 3
    assert collected.volume_available is True
    assert collected.missing_minutes_after == 0


def test_does_not_close_active_candle_before_minute_end() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")
    builder.add_tick(create_tick(0, 30, 1.1000))

    result = builder.close_current_if_elapsed(
        datetime(2026, 11, 2, 10, 0, 59, tzinfo=UTC)
    )

    assert result == ()


def test_closes_active_candle_when_full_minute_has_elapsed() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")
    builder.add_tick(create_tick(0, 30, 1.1000))

    result = builder.close_current_if_elapsed(
        datetime(2026, 11, 2, 10, 1, 0, tzinfo=UTC)
    )

    assert len(result) == 1
    assert result[0].candle.timestamp == datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
    assert result[0].candle.open == 1.1000
    assert result[0].candle.close == 1.1000


def test_marks_volume_as_unavailable_when_any_tick_has_no_volume() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")

    builder.add_tick(create_tick(0, 5, 1.1000, 2.0))
    builder.add_tick(create_tick(0, 30, 1.1005))

    result = builder.add_tick(create_tick(1, 1, 1.1010, 1.0))

    assert result[0].volume_available is False
    assert result[0].candle.volume == 0.0


def test_records_missing_minutes_after_closed_candle() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")

    builder.add_tick(create_tick(0, 5, 1.1000))
    result = builder.add_tick(create_tick(3, 1, 1.1010))

    assert result[0].missing_minutes_after == 2


def test_rejects_duplicate_or_out_of_order_ticks() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")

    builder.add_tick(create_tick(0, 10, 1.1000))

    with pytest.raises(ValueError, match="strictly chronological"):
        builder.add_tick(create_tick(0, 10, 1.1001))


def test_rejects_tick_for_another_symbol() -> None:
    builder = OneMinuteCandleBuilder("EURUSD-OTC")

    tick = MarketTick(
        symbol="GBPUSD-OTC",
        timestamp=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        price=1.2500,
    )

    with pytest.raises(ValueError, match="does not match builder symbol"):
        builder.add_tick(tick)