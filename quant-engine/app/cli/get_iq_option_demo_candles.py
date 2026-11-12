import argparse
import json
import sys
from collections.abc import Sequence

from app.domain.candle import Candle
from app.providers.iq_option_market_data_provider import (
    IqOptionMarketDataProvider,
)

SUPPORTED_OTC_SYMBOLS = (
    "EURUSD-OTC",
    "GBPUSD-OTC",
    "USDJPY-OTC",
    "EURJPY-OTC",
    "EURGBP-OTC",
    "AUDUSD-OTC",
    "USDCAD-OTC",
    "AUDCAD-OTC",
)

SUPPORTED_TIMEFRAMES = ("1m",)


class JsonArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises structured-friendly validation errors."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def candle_to_payload(candle: Candle) -> dict[str, object]:
    """Convert one validated closed IQ Option candle into API JSON."""

    return {
        "timestamp": candle.timestamp.isoformat(),
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
        "closed": True,
    }


def normalize_symbol(symbol: str) -> str:
    """Normalize a user symbol while preserving the OTC suffix."""

    return symbol.strip().upper().replace("/", "")


def get_iq_option_demo_candles(
    symbol: str,
    timeframe: str,
    limit: int,
    provider: IqOptionMarketDataProvider | None = None,
) -> dict[str, object]:
    """Return real closed IQ Option PRACTICE candles for one approved OTC asset."""

    normalized_symbol = normalize_symbol(symbol)

    if normalized_symbol not in SUPPORTED_OTC_SYMBOLS:
        supported_symbols = ", ".join(SUPPORTED_OTC_SYMBOLS)
        raise ValueError(
            "unsupported IQ Option OTC symbol; supported values are: "
            f"{supported_symbols}"
        )

    if timeframe not in SUPPORTED_TIMEFRAMES:
        supported_timeframes = ", ".join(SUPPORTED_TIMEFRAMES)
        raise ValueError(
            "unsupported IQ Option timeframe; supported values are: "
            f"{supported_timeframes}"
        )

    resolved_provider = provider or IqOptionMarketDataProvider()
    candles = resolved_provider.get_candles(
        symbol=normalized_symbol,
        timeframe=timeframe,
        limit=limit,
    )

    if not candles:
        raise LookupError(
            f"IQ Option returned no closed candles for {normalized_symbol} "
            "on PRACTICE"
        )

    return {
        "source": IqOptionMarketDataProvider.source,
        "venue": IqOptionMarketDataProvider.venue,
        "accountMode": "PRACTICE",
        "symbol": normalized_symbol,
        "timeframe": timeframe,
        "candles": [candle_to_payload(candle) for candle in candles],
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
    """Print real closed IQ Option PRACTICE candles as JSON."""

    parser = JsonArgumentParser(
        description=(
            "Retrieve validated closed IQ Option PRACTICE candles for charts."
        ),
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--limit", type=int, default=100)

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