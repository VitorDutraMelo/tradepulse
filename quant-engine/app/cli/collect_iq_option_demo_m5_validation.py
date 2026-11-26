import json
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.cli.get_iq_option_demo_m5_signal import (
    JsonArgumentParser,
    M5_SYMBOL,
    error_to_payload,
)

M5_MINUTES = 5
DEFAULT_GRACE_SECONDS = 90
MINIMUM_GRACE_SECONDS = 15
MAXIMUM_GRACE_SECONDS = 240
DEFAULT_BACKEND_URL = "http://127.0.0.1:3001"
DEFAULT_TIMEOUT_SECONDS = 45


def now_utc() -> datetime:
    return datetime.now(UTC)


def validate_grace_seconds(grace_seconds: int) -> None:
    if not MINIMUM_GRACE_SECONDS <= grace_seconds <= MAXIMUM_GRACE_SECONDS:
        raise ValueError(
            "grace-seconds must be between "
            f"{MINIMUM_GRACE_SECONDS} and {MAXIMUM_GRACE_SECONDS}"
        )


def next_collection_at(
    observed_at: datetime,
    grace_seconds: int,
) -> datetime:
    validate_grace_seconds(grace_seconds)

    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    utc_now = observed_at.astimezone(UTC)
    minute_floor = utc_now.minute - (utc_now.minute % M5_MINUTES)

    current_boundary = utc_now.replace(
        minute=minute_floor,
        second=0,
        microsecond=0,
    )

    current_collection_at = current_boundary + timedelta(
        seconds=grace_seconds,
    )

    if utc_now < current_collection_at:
        return current_collection_at

    return current_collection_at + timedelta(minutes=M5_MINUTES)


def seconds_until_next_collection(
    observed_at: datetime,
    grace_seconds: int,
) -> float:
    scheduled_at = next_collection_at(
        observed_at=observed_at,
        grace_seconds=grace_seconds,
    )

    return max(
        0.0,
        (scheduled_at - observed_at.astimezone(UTC)).total_seconds(),
    )


def build_m5_signal_url(
    backend_url: str,
    symbol: str,
) -> str:
    normalized_backend_url = backend_url.rstrip("/")

    if not normalized_backend_url:
        raise ValueError("backend-url must not be empty")

    query = urlencode({"symbol": symbol})

    return (
        f"{normalized_backend_url}"
        f"/api/v1/iq-option/demo/m5-signal?{query}"
    )


def collect_once(
    symbol: str,
    backend_url: str = DEFAULT_BACKEND_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, object]:
    if timeout_seconds < 1:
        raise ValueError("timeout-seconds must be positive")

    url = build_m5_signal_url(
        backend_url=backend_url,
        symbol=symbol,
    )

    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            raw_payload = response.read().decode("utf-8")
    except HTTPError as error:
        raw_error = error.read().decode("utf-8", errors="replace")

        try:
            error_payload = json.loads(raw_error)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"TradePulse backend returned HTTP {error.code}"
            ) from error

        if isinstance(error_payload, dict):
            nested_error = error_payload.get("error")

            if isinstance(nested_error, dict):
                message = nested_error.get("message")

                if isinstance(message, str) and message:
                    raise RuntimeError(message) from error

        raise RuntimeError(
            f"TradePulse backend returned HTTP {error.code}"
        ) from error
    except URLError as error:
        raise RuntimeError(
            "TradePulse backend is unavailable"
        ) from error

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "TradePulse backend returned invalid JSON"
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            "TradePulse backend returned an invalid payload"
        )

    data = payload.get("data")

    if not isinstance(data, dict):
        raise RuntimeError(
            "TradePulse backend response does not contain data"
        )

    return data


def run_watch(
    symbol: str,
    backend_url: str,
    grace_seconds: int,
    timeout_seconds: int,
    now: Callable[[], datetime] = now_utc,
    sleep: Callable[[float], None] = time.sleep,
    collect: Callable[[str, str, int], dict[str, object]] = collect_once,
    max_runs: int | None = None,
) -> int:
    validate_grace_seconds(grace_seconds)

    completed_runs = 0

    while max_runs is None or completed_runs < max_runs:
        delay_seconds = seconds_until_next_collection(
            observed_at=now(),
            grace_seconds=grace_seconds,
        )

        sleep(delay_seconds)

        try:
            payload = collect(
                symbol,
                backend_url,
                timeout_seconds,
            )
        except RuntimeError as error:
            print(
                json.dumps(error_to_payload(error)),
                file=sys.stderr,
            )
        else:
            print(json.dumps(payload, indent=2))

        completed_runs += 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description=(
            "Schedule local M5 validation checks through the "
            "TradePulse backend cache. This command never sends orders."
        ),
    )
    parser.add_argument("--symbol", default=M5_SYMBOL)
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
    )
    parser.add_argument(
        "--grace-seconds",
        type=int,
        default=DEFAULT_GRACE_SECONDS,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
    )
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--max-runs", type=int)

    try:
        arguments = parser.parse_args(argv)
        validate_grace_seconds(arguments.grace_seconds)

        if arguments.timeout_seconds < 1:
            raise ValueError("timeout-seconds must be positive")

        if arguments.max_runs is not None and arguments.max_runs < 1:
            raise ValueError("max-runs must be positive")

        if arguments.watch:
            return run_watch(
                symbol=arguments.symbol,
                backend_url=arguments.backend_url,
                grace_seconds=arguments.grace_seconds,
                timeout_seconds=arguments.timeout_seconds,
                max_runs=arguments.max_runs,
            )

        payload = collect_once(
            symbol=arguments.symbol,
            backend_url=arguments.backend_url,
            timeout_seconds=arguments.timeout_seconds,
        )
    except (RuntimeError, ValueError) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
