import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.domain.signal import Signal
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)
from app.repositories.iq_option_demo_analysis_repository import (
    IqOptionDemoAnalysisRepository,
)
from app.strategies.ema_crossover_strategy import EmaCrossoverStrategy

DEFAULT_ANALYSIS_DIRECTORY = Path("data/iq-option-demo-analyses")


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises structured-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def signal_to_payload(signal: Signal) -> dict[str, object]:
    """Convert an IQ Option technical Signal into JSON-safe terminal output."""

    return {
        "symbol": signal.symbol,
        "timeframe": signal.timeframe,
        "timestamp": signal.timestamp.isoformat(),
        "direction": signal.direction.value,
        "score": signal.score,
        "reasons": list(signal.reasons),
        "source": IqOptionMarketDataProvider.source,
        "venue": IqOptionMarketDataProvider.venue,
        "accountMode": "PRACTICE",
        "strategy": "ema_crossover",
        "indicators": {
            "fastEmaPeriod": 9,
            "slowEmaPeriod": 21,
        },
        "disclaimer": (
            "Technical analysis only. LONG, SHORT and NEUTRAL are not "
            "automatic CALL, PUT or WAIT instructions."
        ),
    }


def analyze_iq_option_market(
    symbol: str,
    timeframe: str,
    limit: int,
    provider: IqOptionMarketDataProvider | None = None,
    analysis_repository: IqOptionDemoAnalysisRepository | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    """Analyze and persist closed IQ Option DEMO candles with EMA 9/21 and RSI 14."""

    resolved_provider = provider or IqOptionMarketDataProvider()
    candles = tuple(
        resolved_provider.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
    )
    strategy = EmaCrossoverStrategy(rsi_period=14)
    signal = strategy.analyze(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
    )
    payload = signal_to_payload(signal)

    resolved_repository = analysis_repository or IqOptionDemoAnalysisRepository(
        DEFAULT_ANALYSIS_DIRECTORY
    )
    recorded_at = (now or (lambda: datetime.now(tz=UTC)))()
    record_path = resolved_repository.save(
        signal=signal,
        candles=candles,
        recorded_at=recorded_at,
    )

    return {
        **payload,
        "recordId": record_path.stem,
    }


def list_iq_option_symbols(
    provider: IqOptionMarketDataProvider | None = None,
) -> dict[str, object]:
    """Return currently open IQ Option DEMO symbols from the provider."""

    resolved_provider = provider or IqOptionMarketDataProvider()

    return {
        "source": IqOptionMarketDataProvider.source,
        "venue": IqOptionMarketDataProvider.venue,
        "accountMode": "PRACTICE",
        "symbols": list(resolved_provider.get_symbols()),
    }


def error_to_payload(error: Exception) -> dict[str, object]:
    """Convert expected IQ Option CLI errors into structured JSON."""

    if isinstance(error, PermissionError):
        code = "IQ_OPTION_ACCESS_DENIED"
    elif isinstance(error, ConnectionError):
        code = "IQ_OPTION_UNAVAILABLE"
    elif isinstance(error, LookupError):
        code = "IQ_OPTION_MARKET_NOT_FOUND"
    elif isinstance(error, RuntimeError):
        code = "IQ_OPTION_PROVIDER_UNAVAILABLE"
    else:
        code = "INVALID_IQ_OPTION_ANALYSIS_REQUEST"

    return {
        "error": {
            "code": code,
            "message": str(error),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run an IQ Option DEMO analysis or list available symbols."""

    parser = JsonArgumentParser(
        description=(
            "Analyze IQ Option DEMO candles with TradePulse EMA 9/21 and RSI 14."
        ),
    )
    requested_action = parser.add_mutually_exclusive_group(required=True)
    requested_action.add_argument("--symbol")
    requested_action.add_argument(
        "--list-symbols",
        action="store_true",
    )
    parser.add_argument("--timeframe", default="1m")
    parser.add_argument("--limit", type=int, default=100)

    try:
        arguments = parser.parse_args(argv)

        if arguments.list_symbols:
            payload = list_iq_option_symbols()
        else:
            payload = analyze_iq_option_market(
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
