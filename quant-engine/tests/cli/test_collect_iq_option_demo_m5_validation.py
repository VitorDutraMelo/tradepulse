from datetime import UTC, datetime, timedelta

from app.cli.collect_iq_option_demo_m5_validation import (
    build_m5_signal_url,
    next_collection_at,
    run_watch,
    seconds_until_next_collection,
)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)

    sleeps: list[float]


def make_clock(start: datetime) -> FakeClock:
    clock = FakeClock(start)
    clock.sleeps = []
    return clock


def payload_for(close: datetime) -> dict[str, object]:
    return {
        "symbol": "GBPUSD-OTC",
        "latestClosedCandle": {"closeTime": close.isoformat()},
        "decision": {"action": "WAIT"},
    }


def test_builds_a_local_backend_m5_signal_url() -> None:
    url = build_m5_signal_url(
        backend_url="http://127.0.0.1:3001/",
        symbol="GBPUSD-OTC",
    )

    assert url == (
        "http://127.0.0.1:3001/"
        "api/v1/iq-option/demo/m5-signal?symbol=GBPUSD-OTC"
    )


def test_schedules_exactly_at_the_next_m5_close_without_grace() -> None:
    scheduled_at = next_collection_at(datetime(2026, 11, 21, 16, 2, tzinfo=UTC))

    assert scheduled_at == datetime(2026, 11, 21, 16, 5, tzinfo=UTC)


def test_a_boundary_instant_is_collected_immediately() -> None:
    boundary = datetime(2026, 11, 21, 16, 5, tzinfo=UTC)

    assert next_collection_at(boundary) == boundary
    assert seconds_until_next_collection(boundary) == 0


def test_calculates_wait_duration_until_the_close() -> None:
    delay = seconds_until_next_collection(datetime(2026, 11, 21, 16, 4, 30, tzinfo=UTC))

    assert delay == 30


def test_watch_stops_as_soon_as_the_new_candle_is_published() -> None:
    clock = make_clock(datetime(2026, 11, 21, 16, 4, 30, tzinfo=UTC))
    boundary = datetime(2026, 11, 21, 16, 5, tzinfo=UTC)
    responses = [
        payload_for(boundary - timedelta(minutes=5)),  # previous candle: keep trying
        payload_for(boundary),
    ]
    calls: list[datetime] = []

    def collect(symbol: str, backend_url: str, timeout_seconds: int) -> dict[str, object]:
        calls.append(clock.now())
        return responses.pop(0)

    exit_code = run_watch(
        symbol="GBPUSD-OTC",
        backend_url="http://127.0.0.1:3001",
        timeout_seconds=45,
        now=clock.now,
        sleep=clock.sleep,
        collect=collect,
        max_runs=1,
    )

    assert exit_code == 0
    assert calls == [boundary, boundary + timedelta(seconds=1)]
    assert clock.sleeps == [30, 1.0]


def test_watch_never_waits_a_fixed_ninety_seconds() -> None:
    clock = make_clock(datetime(2026, 11, 21, 16, 4, 59, tzinfo=UTC))
    boundary = datetime(2026, 11, 21, 16, 5, tzinfo=UTC)

    run_watch(
        symbol="GBPUSD-OTC",
        backend_url="http://127.0.0.1:3001",
        timeout_seconds=45,
        now=clock.now,
        sleep=clock.sleep,
        collect=lambda *_: payload_for(boundary),
        max_runs=1,
    )

    assert clock.sleeps == [1]
    assert max(clock.sleeps) < 90


def test_watch_gives_up_at_the_next_boundary(capsys) -> None:
    clock = make_clock(datetime(2026, 11, 21, 16, 5, tzinfo=UTC))
    stale = payload_for(datetime(2026, 11, 21, 16, 0, tzinfo=UTC))

    run_watch(
        symbol="GBPUSD-OTC",
        backend_url="http://127.0.0.1:3001",
        timeout_seconds=45,
        now=clock.now,
        sleep=clock.sleep,
        collect=lambda *_: stale,
        max_runs=1,
    )

    assert "M5_CANDLE_NOT_PUBLISHED" in capsys.readouterr().err
    assert clock.now() < datetime(2026, 11, 21, 16, 10, tzinfo=UTC)
