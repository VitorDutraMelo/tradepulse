import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from app.domain.candle import Candle
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)

M5_SYMBOL = "GBPUSD-OTC"
M5_TIMEFRAME = "5m"
M5_INTERVAL_SECONDS = 300
M5_FETCH_LIMIT = 3


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises JSON-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def now_utc() -> datetime:
    """Return the application UTC clock used for observable timings."""

    return datetime.now(tz=UTC)


def duration_ms(started_at: datetime, completed_at: datetime) -> float:
    """Return a non-negative UTC duration in milliseconds."""

    return max(
        0.0,
        round((completed_at - started_at).total_seconds() * 1000, 3),
    )


def normalize_symbol(symbol: str) -> str:
    """Normalize the only supported first-delivery M5 symbol."""

    return symbol.strip().upper().replace("/", "")


def candle_close_time(candle: Candle) -> datetime:
    """Derive M5 close from the source candle open timestamp and interval."""

    return candle.timestamp + timedelta(seconds=M5_INTERVAL_SECONDS)


def expected_latest_close_time(observed_at: datetime) -> datetime:
    """Return the most recent completed M5 boundary according to UTC clock."""

    epoch_seconds = int(observed_at.timestamp())
    rounded_seconds = epoch_seconds - (epoch_seconds % M5_INTERVAL_SECONDS)

    return datetime.fromtimestamp(rounded_seconds, tz=UTC)


def determine_state(
    latest_close_time: datetime,
    expected_close_time: datetime,
) -> str:
    """Classify freshness without inventing a fixed waiting delay."""

    if latest_close_time >= expected_close_time:
        return "UPDATED"

    if latest_close_time == (
        expected_close_time - timedelta(seconds=M5_INTERVAL_SECONDS)
    ):
        return "AWAITING_CONFIRMATION"

    return "STALE"


def candle_to_payload(candle: Candle) -> dict[str, object]:
    """Convert one confirmed M5 candle to the API contract."""

    close_time = candle_close_time(candle)

    return {
        "timestamp": candle.timestamp.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "closed": True,
        "closeTime": close_time.isoformat(),
    }


def get_iq_option_demo_m5_sync(
    symbol: str,
    provider: IqOptionMarketDataProvider | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Return one verified M5 synchronization snapshot from IQ Option PRACTICE.

    The iqoptionapi integration does not expose the precise instant at which
    IQ Option made a closed candle available. That value is intentionally
    represented as null instead of being inferred.
    """

    resolved_now = now or now_utc
    normalized_symbol = normalize_symbol(symbol)

    if normalized_symbol != M5_SYMBOL:
        raise ValueError(
            "only GBPUSD-OTC is available for the first M5 synchronization "
            "demonstration"
        )

    analysis_started_at = resolved_now()
    provider_call_started_at = resolved_now()
    resolved_provider = provider or IqOptionMarketDataProvider()

    candles = tuple(
        resolved_provider.get_candles(
            symbol=M5_SYMBOL,
            timeframe=M5_TIMEFRAME,
            limit=M5_FETCH_LIMIT,
        )
    )

    provider_call_completed_at = resolved_now()

    if not candles:
        raise LookupError("IQ Option returned no closed M5 candles for GBPUSD-OTC")

    latest_candle = max(candles, key=lambda candle: candle.timestamp)
    latest_close_time = candle_close_time(latest_candle)
    expected_close_time = expected_latest_close_time(provider_call_completed_at)
    state = determine_state(latest_close_time, expected_close_time)
    observed_age_seconds = max(
        0.0,
        round(
            (provider_call_completed_at - latest_close_time).total_seconds(),
            3,
        ),
    )

    payload_built_at = resolved_now()

    return {
        "source": IqOptionMarketDataProvider.source,
        "venue": IqOptionMarketDataProvider.venue,
        "accountMode": "PRACTICE",
        "symbol": M5_SYMBOL,
        "timeframe": M5_TIMEFRAME,
        "state": state,
        "latestClosedCandle": candle_to_payload(latest_candle),
        "expectedLatestCloseTime": expected_close_time.isoformat(),
        "timing": {
            "clockSource": "application_utc_clock",
            "iqCandleAvailabilityAt": None,
            "iqCandleAvailabilityMeasurement": (
                "NOT_AVAILABLE_FROM_IQ_OPTION_API"
            ),
            "sourceCandleCloseTime": latest_close_time.isoformat(),
            "observedClosedCandleAgeSeconds": observed_age_seconds,
            "python": {
                "analysisStartedAt": analysis_started_at.isoformat(),
                "providerCallStartedAt": provider_call_started_at.isoformat(),
                "providerCallCompletedAt": provider_call_completed_at.isoformat(),
                "payloadBuiltAt": payload_built_at.isoformat(),
                "providerCallDurationMs": duration_ms(
                    provider_call_started_at,
                    provider_call_completed_at,
                ),
                "payloadProcessingDurationMs": duration_ms(
                    provider_call_completed_at,
                    payload_built_at,
                ),
                "totalDurationMs": duration_ms(
                    analysis_started_at,
                    payload_built_at,
                ),
                "providerCallScope": (
                    "IQ Option connection, candle retrieval and provider parsing"
                ),
            },
        },
    }


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected provider errors to structured stderr JSON."""

    if isinstance(error, PermissionError):
        code = "IQ_OPTION_ACCESS_DENIED"
    elif isinstance(error, ConnectionError):
        code = "IQ_OPTION_UNAVAILABLE"
    elif isinstance(error, LookupError):
        code = "IQ_OPTION_M5_CANDLE_UNAVAILABLE"
    else:
        code = "INVALID_IQ_OPTION_M5_SYNC_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print a read-only M5 synchronization snapshot as JSON."""

    parser = JsonArgumentParser(
        description="Synchronize the latest closed GBPUSD-OTC M5 candle.",
    )
    parser.add_argument("--symbol", default=M5_SYMBOL)

    try:
        arguments = parser.parse_args(argv)
        payload = get_iq_option_demo_m5_sync(symbol=arguments.symbol)
    except (
        ConnectionError,
        LookupError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())