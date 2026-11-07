import argparse
import json
import sys
from collections.abc import Sequence
from datetime import timedelta

from app.domain.candle import Candle
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)

TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
}


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises structured-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def candle_to_payload(
    candle: Candle,
    timeframe: str,
) -> dict[str, object]:
    """Convert one validated closed IQ Option candle into terminal JSON."""

    interval_seconds = TIMEFRAME_SECONDS.get(timeframe)

    if interval_seconds is None:
        supported_timeframes = ", ".join(TIMEFRAME_SECONDS)
        raise ValueError(
            "unsupported IQ Option timeframe; supported values are: "
            f"{supported_timeframes}"
        )

    return {
        "openTimestamp": candle.timestamp.isoformat(),
        "closeTimestamp": (
            candle.timestamp + timedelta(seconds=interval_seconds)
        ).isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "closed": True,
    }


def get_iq_option_demo_candles(
    symbol: str,
    timeframe: str,
    limit: int,
    provider: IqOptionMarketDataProvider | None = None,
) -> dict[str, object]:
    """Return validated closed IQ Option DEMO candles for chart comparison."""

    normalized_symbol = symbol.strip().upper().replace("/", "")
    resolved_provider = provider or IqOptionMarketDataProvider()
    candles = resolved_provider.get_candles(
        symbol=normalized_symbol,
        timeframe=timeframe,
        limit=limit,
    )

    return {
        "symbol": normalized_symbol,
        "timeframe": timeframe,
        "source": IqOptionMarketDataProvider.source,
        "venue": IqOptionMarketDataProvider.venue,
        "accountMode": "PRACTICE",
        "candles": [
            candle_to_payload(
                candle=candle,
                timeframe=timeframe,
            )
            for candle in candles
        ],
    }


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected IQ Option candle errors into structured JSON."""

    if isinstance(error, PermissionError):
        code = "IQ_OPTION_ACCESS_DENIED"
    elif isinstance(error, ConnectionError):
        code = "IQ_OPTION_UNAVAILABLE"
    elif isinstance(error, LookupError):
        code = "IQ_OPTION_MARKET_NOT_FOUND"
    elif isinstance(error, RuntimeError):
        code = "IQ_OPTION_PROVIDER_UNAVAILABLE"
    else:
        code = "INVALID_IQ_OPTION_CANDLE_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Print validated closed IQ Option DEMO candles as readable JSON."""

    parser = JsonArgumentParser(
        description=(
            "Retrieve validated closed IQ Option DEMO candles for comparison."
        ),
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--limit", type=int, default=5)

    try:
        arguments = parser.parse_args(argv)
        payload = get_iq_option_demo_candles(
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            limit=arguments.limit,
        )
    except (
        ConnectionError,
        LookupError,
        PermissionError,
        RuntimeError,
        ValueError,
    ) as error:
        print(json.dumps(error_to_payload(error), indent=2), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())