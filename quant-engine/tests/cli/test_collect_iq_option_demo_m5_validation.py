from datetime import UTC, datetime

from app.cli.collect_iq_option_demo_m5_validation import (
    build_m5_signal_url,
    next_collection_at,
    run_watch,
    seconds_until_next_collection,
)


def test_builds_a_local_backend_m5_signal_url() -> None:
    url = build_m5_signal_url(
        backend_url="http://127.0.0.1:3001/",
        symbol="GBPUSD-OTC",
    )

    assert url == (
        "http://127.0.0.1:3001/"
        "api/v1/iq-option/demo/m5-signal?symbol=GBPUSD-OTC"
    )


def test_schedules_after_m5_close_plus_grace() -> None:
    scheduled_at = next_collection_at(
        observed_at=datetime(
            2026,
            11,
            21,
            16,
            2,
            tzinfo=UTC,
        ),
        grace_seconds=90,
    )

    assert scheduled_at == datetime(
        2026,
        11,
        21,
        16,
        6,
        30,
        tzinfo=UTC,
    )


def test_calculates_wait_duration() -> None:
    delay = seconds_until_next_collection(
        observed_at=datetime(
            2026,
            11,
            21,
            16,
            4,
            30,
            tzinfo=UTC,
        ),
        grace_seconds=90,
    )

    assert delay == 120


def test_watch_calls_the_local_backend_once_per_cycle() -> None:
    sleeps: list[float] = []
    calls: list[tuple[str, str, int]] = []

    def collect(
        symbol: str,
        backend_url: str,
        timeout_seconds: int,
    ) -> dict[str, object]:
        calls.append((symbol, backend_url, timeout_seconds))

        return {
            "symbol": symbol,
            "decision": {
                "action": "WAIT",
            },
        }

    exit_code = run_watch(
        symbol="GBPUSD-OTC",
        backend_url="http://127.0.0.1:3001",
        grace_seconds=90,
        timeout_seconds=45,
        now=lambda: datetime(
            2026,
            11,
            21,
            16,
            4,
            30,
            tzinfo=UTC,
        ),
        sleep=sleeps.append,
        collect=collect,
        max_runs=1,
    )

    assert exit_code == 0
    assert sleeps == [120]
    assert calls == [
        (
            "GBPUSD-OTC",
            "http://127.0.0.1:3001",
            45,
        )
    ]
