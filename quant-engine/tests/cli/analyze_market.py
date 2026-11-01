import argparse
import json
import sys
from collections.abc import Sequence

from app.domain.signal import Signal
from app.providers.binance_market_data_provider import BinanceMarketDataProvider
from app.signals.market_analysis_service import MarketAnalysisService
from app.strategies.ema_crossover_strategy import EmaCrossoverStrategy


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises structured-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def signal_to_payload(signal: Signal) -> dict[str, object]:
    """Convert an internal Signal into JSON-safe API data."""
    return {
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "timestamp": signal.timestamp.isoformat(),
        "direction": signal.direction.value,
        "score": signal.score,
        "reasons": list(signal.reasons),
        "source": "binance_spot",
        "strategy": "ema_crossover",
        "indicators": {
            "fastEmaPeriod": 9,
            "slowEmaPeriod": 21,
        },
    }


def analyze_market(symbol: str, timeframe: str, limit: int) -> dict[str, object]:
    """Analyze real Binance Spot data and return a JSON-safe signal payload."""
    service = MarketAnalysisService(
        provider=BinanceMarketDataProvider(),
        strategy=EmaCrossoverStrategy(),
    )
    signal = service.analyze(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )

    return signal_to_payload(signal)


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected CLI errors into structured JSON for stderr."""
    if isinstance(error, ConnectionError):
        code = "MARKET_DATA_UNAVAILABLE"
    elif isinstance(error, LookupError):
        code = "MARKET_DATA_NOT_FOUND"
    else:
        code = "INVALID_ANALYSIS_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run a market analysis and write only JSON to the process streams."""
    parser = JsonArgumentParser(
        description="Generate a TradePulse market-analysis signal.",
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--limit", type=int, default=100)

    try:
        arguments = parser.parse_args(argv)
        payload = analyze_market(
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