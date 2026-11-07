import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime

from app.domain.iq_option_binary_signal import IqOptionBinarySignal
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)
from app.strategies.iq_option_trend_strategy import IqOptionTrendStrategy


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises JSON-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def signal_to_payload(signal: IqOptionBinarySignal) -> dict[str, object]:
    """Convert the read-only IQ Option binary reference into JSON."""
    return {
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "source": signal.source,
        "accountMode": "PRACTICE",
        "analysisAt": signal.analysis_at.isoformat(),
        "lastClosedCandle": {
            "openTime": (
                signal.last_candle_open_time.isoformat()
                if signal.last_candle_open_time is not None
                else None
            ),
            "closeTime": (
                signal.last_candle_close_time.isoformat()
                if signal.last_candle_close_time is not None
                else None
            ),
            "ageSeconds": signal.last_candle_age_seconds,
        },
        "indicators": {
            "ema9": signal.ema_fast,
            "ema21": signal.ema_slow,
            "rsi14": signal.rsi,
            "adx14": signal.adx,
            "atr14": signal.atr,
        },
        "action": signal.action.value,
        "reference": {
            "price": signal.reference_price,
            "entryTime": (
                signal.reference_entry_time.isoformat()
                if signal.reference_entry_time is not None
                else None
            ),
            "expirationTime": (
                signal.reference_expiration_time.isoformat()
                if signal.reference_expiration_time is not None
                else None
            ),
        },
        "reasons": list(signal.reasons),
        "disclaimer": (
            "Technical reference only. No IQ Option order was sent. "
            "CALL, PUT and WAIT are not profit guarantees or probabilities."
        ),
    }


def analyze_iq_option_binary_signal(
    symbol: str,
    timeframe: str,
    limit: int,
    max_candle_age_seconds: int,
) -> dict[str, object]:
    """Analyze closed IQ Option DEMO candles without executing an order."""
    provider = IqOptionMarketDataProvider()
    candles = provider.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )
    strategy = IqOptionTrendStrategy(
        max_candle_age_seconds=max_candle_age_seconds,
    )
    signal = strategy.analyze(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        source=provider.source,
        analysis_at=datetime.now(tz=UTC),
    )

    return signal_to_payload(signal)


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected failures to JSON written on stderr."""
    if isinstance(error, PermissionError):
        code = "IQ_OPTION_ACCESS_DENIED"
    elif isinstance(error, ConnectionError):
        code = "IQ_OPTION_DATA_UNAVAILABLE"
    else:
        code = "INVALID_IQ_OPTION_ANALYSIS_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run a read-only IQ Option DEMO binary technical analysis."""
    parser = JsonArgumentParser(
        description="Analyze IQ Option DEMO candles without sending an order.",
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--max-candle-age-seconds",
        type=int,
        default=120,
    )

    try:
        arguments = parser.parse_args(argv)
        payload = analyze_iq_option_binary_signal(
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            limit=arguments.limit,
            max_candle_age_seconds=arguments.max_candle_age_seconds,
        )
    except (ConnectionError, PermissionError, ValueError) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())