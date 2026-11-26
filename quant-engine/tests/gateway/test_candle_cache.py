from gateway_fakes import FakeClock, FakeTransport, utc

from app.gateway.candle_cache import CandleCache
from app.gateway.provider import SessionBackedProvider
from app.gateway.session import IqSession


def build(clock: FakeClock, interval: int = 60):
    transports: list[FakeTransport] = []

    def factory(email: str, password: str) -> FakeTransport:
        transport = FakeTransport(clock, interval_seconds=interval)
        transports.append(transport)
        return transport

    session = IqSession(
        email="owner@example.com",
        password="pw-123",
        transport_factory=factory,
        clock=clock.now,
        monotonic=clock.monotonic,
    )
    return CandleCache(session, monotonic=clock.monotonic, min_refetch_seconds=1.0), transports


def test_same_candle_is_served_from_cache_without_new_requests() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 5))
    cache, transports = build(clock)

    first = cache.get("EURUSD-OTC", "1m", 120)
    clock.advance(10)
    second = cache.get("EURUSD-OTC", "1m", 100)  # chart reuses analysis data

    assert first.cache_hit is False
    assert second.cache_hit is True
    assert len(second.candles) == 100
    assert len(transports[0].candle_requests) == 1
    assert second.freshness == "CURRENT"


def test_a_new_candle_boundary_forces_a_new_request() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 5))
    cache, transports = build(clock)

    cache.get("EURUSD-OTC", "1m", 30)
    clock.advance(60)
    result = cache.get("EURUSD-OTC", "1m", 30)

    assert result.cache_hit is False
    assert len(transports[0].candle_requests) == 2
    assert result.latest_close == utc(2026, 11, 26, 12, 4)


def test_old_series_is_reported_as_awaiting_never_as_current() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 5))
    cache, _ = build(clock)
    cache.get("EURUSD-OTC", "1m", 30)

    # The 12:04 boundary has passed but less than min_refetch since last fetch.
    clock.current = utc(2026, 11, 26, 12, 4, 0, 200000)
    result = cache.get("EURUSD-OTC", "1m", 30)

    assert result.cache_hit is True
    assert result.freshness == "AWAITING_CLOSE_PUBLICATION"
    assert result.latest_close == utc(2026, 11, 26, 12, 3)


def test_retries_are_paced_while_the_close_is_not_published() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 59, 900000))
    cache, transports = build(clock)
    cache.get("EURUSD-OTC", "1m", 30)

    for _ in range(10):  # ten reads within the same 1 s window
        clock.advance(0.05)
        cache.get("EURUSD-OTC", "1m", 30)

    assert len(transports[0].candle_requests) == 1

    clock.advance(1.0)
    cache.get("EURUSD-OTC", "1m", 30)
    assert len(transports[0].candle_requests) == 2


def test_symbols_and_timeframes_are_cached_independently() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 5, 5))
    cache, transports = build(clock)

    cache.get("EURUSD-OTC", "1m", 10)
    cache.get("GBPUSD-OTC", "1m", 10)
    cache.get("EURUSD-OTC", "5m", 10)

    assert len(transports[0].candle_requests) == 3


def test_provider_records_observed_timings_for_the_analysis() -> None:
    clock = FakeClock(utc(2026, 11, 26, 12, 3, 5))
    cache, _ = build(clock)
    provider = SessionBackedProvider(cache)

    provider.get_candles(symbol="EURUSD-OTC", timeframe="1m", limit=20)
    meta = provider.fetch_metadata()[0]

    assert meta["latestClosedCandle"]["candleId"] == "EURUSD-OTC:1m:1795694520"
    assert meta["latestClosedCandle"]["closeTime"] == "2026-11-26T12:03:00+00:00"
    assert meta["latestClosedCandle"]["sourceCloseTimeKind"] == "OBSERVED_SOURCE_FIELD"
    assert meta["receivedAt"] == "2026-11-26T12:03:05+00:00"
    assert meta["observedQuote"]["sourceTimestampKind"] == "OBSERVED_SOURCE"
