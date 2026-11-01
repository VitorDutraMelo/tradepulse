import argparse
import json
import sys
from collections.abc import Sequence

from app.domain.candle import Candle
from app.providers.binance_market_data_provider import BinanceMarketDataProvider


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises structured-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def candle_to_payload(candle: Candle) -> dict[str, object]:
    """Convert an internal Candle into JSON-safe API data."""
    return {
        "timestamp": candle.timestamp.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


def get_market_candles(
    symbol: str,
    timeframe: str,
    limit: int,
) -> dict[str, object]:
    """Retrieve closed Binance Spot candles as a JSON-safe payload."""
    provider = BinanceMarketDataProvider()
    candles = provider.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "source": "binance_spot",
        "candles": [candle_to_payload(candle) for candle in candles],
    }


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected CLI errors into structured JSON for stderr."""
    if isinstance(error, ConnectionError):
        code = "MARKET_DATA_UNAVAILABLE"
    elif isinstance(error, LookupError):
        code = "MARKET_DATA_NOT_FOUND"
    else:
        code = "INVALID_MARKET_DATA_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Retrieve market candles and write only JSON to the process streams."""
    parser = JsonArgumentParser(
        description="Retrieve closed TradePulse market candles.",
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--limit", type=int, default=100)

    try:
        arguments = parser.parse_args(argv)
        payload = get_market_candles(
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            limit=arguments.limit,
        )
    except (ConnectionError, LookupError, ValueError) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())