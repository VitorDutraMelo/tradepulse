import json
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.cli.get_iq_option_demo_m5_signal import (
    M5_SYMBOL,
    JsonArgumentParser,
    error_to_payload,
)

M5_MINUTES = 5
M5_INTERVAL = timedelta(minutes=M5_MINUTES)
DEFAULT_BACKEND_URL = "http://127.0.0.1:3001"
DEFAULT_TIMEOUT_SECONDS = 45

# Controlled retry pacing while the backend has not yet published the candle
# that just closed. This is NOT a fixed waiting delay: the first request is
# sent exactly at the M5 boundary and the loop stops as soon as the candle is
# available (A.2 removed the former 90 s grace period).
RETRY_SCHEDULE_SECONDS = (1.0, 1.0, 2.0, 3.0, 5.0)
MAX_RETRY_INTERVAL_SECONDS = 5.0


def now_utc() -> datetime:
    return datetime.now(UTC)


def _to_utc(observed_at: datetime) -> datetime:
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")

    return observed_at.astimezone(UTC)


def next_collection_at(observed_at: datetime) -> datetime:
    """Return the next M5 boundary (the next candle close), with no grace."""

    utc_now = _to_utc(observed_at)
    minute_floor = utc_now.minute - (utc_now.minute % M5_MINUTES)
    current_boundary = utc_now.replace(minute=minute_floor, second=0, microsecond=0)

    if utc_now == current_boundary:
        return current_boundary

    return current_boundary + M5_INTERVAL


def seconds_until_next_collection(observed_at: datetime) -> float:
    scheduled_at = next_collection_at(observed_at)

    return max(0.0, (scheduled_at - _to_utc(observed_at)).total_seconds())


def retry_delay(attempt: int) -> float:
    if attempt < len(RETRY_SCHEDULE_SECONDS):
        return RETRY_SCHEDULE_SECONDS[attempt]

    return MAX_RETRY_INTERVAL_SECONDS


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


def payload_close_time(payload: dict[str, object]) -> datetime | None:
    candle = payload.get("latestClosedCandle")

    if not isinstance(candle, dict) or not isinstance(candle.get("closeTime"), str):
        return None

    try:
        return _to_utc(datetime.fromisoformat(str(candle["closeTime"])))
    except ValueError:
        return None


def run_watch(
    symbol: str,
    backend_url: str,
    timeout_seconds: int,
    now: Callable[[], datetime] = now_utc,
    sleep: Callable[[float], None] = time.sleep,
    collect: Callable[[str, str, int], dict[str, object]] = collect_once,
    max_runs: int | None = None,
) -> int:
    completed_runs = 0

    while max_runs is None or completed_runs < max_runs:
        boundary = next_collection_at(now())
        sleep(seconds_until_next_collection(now()))

        attempt = 0

        while True:
            try:
                payload: dict[str, object] | None = collect(
                    symbol,
                    backend_url,
                    timeout_seconds,
                )
            except RuntimeError as error:
                print(json.dumps(error_to_payload(error)), file=sys.stderr)
                payload = None

            close_time = payload_close_time(payload) if payload is not None else None

            if close_time is not None and close_time >= boundary:
                print(json.dumps(payload, indent=2))
                break

            delay = retry_delay(attempt)
            attempt += 1

            if _to_utc(now()) + timedelta(seconds=delay) >= boundary + M5_INTERVAL:
                print(
                    json.dumps(
                        {
                            "error": {
                                "code": "M5_CANDLE_NOT_PUBLISHED",
                                "message": (
                                    "the M5 candle closing at "
                                    f"{boundary.isoformat()} was not published "
                                    "before the next boundary"
                                ),
                            }
                        }
                    ),
                    file=sys.stderr,
                )
                break

            sleep(delay)

        completed_runs += 1

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description=(
            "Follow M5 closes through the TradePulse backend. The first request is "
            "sent at each M5 boundary; retries stop as soon as the closed candle is "
            "published. This command never sends orders."
        ),
    )
    parser.add_argument("--symbol", default=M5_SYMBOL)
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
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

        if arguments.timeout_seconds < 1:
            raise ValueError("timeout-seconds must be positive")

        if arguments.max_runs is not None and arguments.max_runs < 1:
            raise ValueError("max-runs must be positive")

        if arguments.watch:
            return run_watch(
                symbol=arguments.symbol,
                backend_url=arguments.backend_url,
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
