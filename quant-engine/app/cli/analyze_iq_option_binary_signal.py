import argparse
import json
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from app.domain.iq_option_binary_signal import IqOptionBinarySignal
from app.domain.trade_signal import TradeAction
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)
from app.repositories.iq_option_demo_binary_signal_repository import (
    IqOptionDemoBinarySignalRepository,
)
from app.strategies.iq_option_trend_strategy import IqOptionTrendStrategy

DEFAULT_BINARY_SIGNAL_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "data/iq-option-demo-binary-signals"
)


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises JSON-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def signal_to_payload(
    signal: IqOptionBinarySignal,
    tracking: dict[str, object] | None = None,
) -> dict[str, object]:
    """Convert the read-only IQ Option binary reference into JSON."""

    payload: dict[str, object] = {
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
            "CALL, PUT and WAIT are not profit guarantees or probabilities. "
            "WIN, LOSS and DRAW are technical candle comparisons only."
        ),
    }

    if tracking is not None:
        payload["tracking"] = tracking

    return payload


def analyze_iq_option_binary_signal(
    symbol: str,
    timeframe: str,
    limit: int,
    max_candle_age_seconds: int,
    provider: IqOptionMarketDataProvider | None = None,
    analysis_repository: IqOptionDemoBinarySignalRepository | None = None,
    now: Callable[[], datetime] | None = None,
    strategy: IqOptionTrendStrategy | None = None,
) -> dict[str, object]:
    """Analyze DEMO candles and track technical CALL/PUT references.

    No IQ Option order is ever sent. Pending references are checked on every
    analysis for the same symbol/timeframe, including when the new result is
    WAIT. If local tracking has a problem, market analysis remains available.
    """

    resolved_provider = provider or IqOptionMarketDataProvider()
    analysis_at = (now or (lambda: datetime.now(tz=UTC)))()

    if analysis_at.tzinfo is None or analysis_at.utcoffset() is None:
        raise ValueError("analysis clock must return a timezone-aware datetime")

    analysis_at = analysis_at.astimezone(UTC)

    candles = tuple(
        resolved_provider.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )
    )

    resolved_strategy = strategy or IqOptionTrendStrategy(
        max_candle_age_seconds=max_candle_age_seconds,
    )

    signal = resolved_strategy.analyze(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        source=resolved_provider.source,
        analysis_at=analysis_at,
    )

    resolved_repository = analysis_repository or IqOptionDemoBinarySignalRepository(
        DEFAULT_BINARY_SIGNAL_DIRECTORY
    )

    try:
        resolved_repository.settle_due_references(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            candles=candles,
            settled_at=analysis_at,
        )
    except (OSError, ValueError):
        if signal.action is not TradeAction.WAIT:
            return signal_to_payload(
                signal,
                {
                    "recordId": None,
                    "status": "UNAVAILABLE",
                    "settledAt": None,
                    "settlementPrice": None,
                },
            )

    if signal.action is TradeAction.WAIT:
        return signal_to_payload(
            signal,
            {
                "recordId": None,
                "status": "NOT_APPLICABLE",
                "settledAt": None,
                "settlementPrice": None,
            },
        )

    try:
        record_path = resolved_repository.save_pending(
            signal=signal,
            recorded_at=analysis_at,
        )
        tracking = resolved_repository.get_tracking(record_path.stem)
    except (OSError, ValueError):
        tracking = {
            "recordId": None,
            "status": "UNAVAILABLE",
            "settledAt": None,
            "settlementPrice": None,
        }

    return signal_to_payload(signal, tracking)


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
