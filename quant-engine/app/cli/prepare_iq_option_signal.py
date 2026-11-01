import json
import sys
from collections.abc import Sequence

from app.cli.analyze_market import JsonArgumentParser, error_to_payload
from app.domain.trade_signal import MarketCategory, TradeSignal
from app.providers.binance_market_data_provider import BinanceMarketDataProvider
from app.signals.iq_option_signal_service import IqOptionSignalService
from app.signals.market_analysis_service import MarketAnalysisService
from app.strategies.ema_crossover_strategy import EmaCrossoverStrategy


def trade_signal_to_payload(signal: TradeSignal) -> dict[str, object]:
    """Convert a product-level TradeSignal into JSON-safe CLI data."""
    return {
        "platform": signal.platform.value,
        "asset": signal.asset,
        "market": signal.market.value,
        "timeframe": signal.timeframe,
        "timestamp": signal.timestamp.isoformat(),
        "dataSource": signal.data_source,
        "analysisDirection": signal.analysis_direction.value,
        "action": signal.action.value,
        "entryTime": (
            signal.entry_time.isoformat() if signal.entry_time is not None else None
        ),
        "expirationTime": (
            signal.expiration_time.isoformat()
            if signal.expiration_time is not None
            else None
        ),
        "reasons": list(signal.reasons),
    }


def prepare_iq_option_signal(
    symbol: str,
    timeframe: str,
    limit: int,
    market: MarketCategory,
) -> dict[str, object]:
    """Prepare a non-executable IQ Option manual-decision signal."""
    analysis_service = MarketAnalysisService(
        provider=BinanceMarketDataProvider(),
        strategy=EmaCrossoverStrategy(),
    )
    analysis = analysis_service.analyze(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )
    trade_signal = IqOptionSignalService().prepare(
        analysis=analysis,
        market=market,
        data_source="binance_spot",
    )

    return trade_signal_to_payload(trade_signal)


def main(argv: Sequence[str] | None = None) -> int:
    """Prepare an IQ Option signal and write only JSON to process streams."""
    parser = JsonArgumentParser(
        description="Prepare a non-executable TradePulse IQ Option signal.",
    )
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--timeframe", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument(
        "--market",
        choices=[market.value for market in MarketCategory],
        default=MarketCategory.CRYPTO.value,
    )

    try:
        arguments = parser.parse_args(argv)
        payload = prepare_iq_option_signal(
            symbol=arguments.symbol,
            timeframe=arguments.timeframe,
            limit=arguments.limit,
            market=MarketCategory(arguments.market),
        )
    except (ConnectionError, LookupError, ValueError) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())