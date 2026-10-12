from collections.abc import Mapping, Sequence

from app.domain.candle import Candle
from app.providers.market_data_provider import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """In-memory provider used for deterministic development and tests."""

    def __init__(
        self,
        candles_by_request: Mapping[tuple[str, str], Sequence[Candle]],
    ) -> None:
        self._candles_by_request = {
            request: tuple(candles)
            for request, candles in candles_by_request.items()
        }

    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[Candle]:
        request = (symbol, timeframe)
        candles = self._candles_by_request.get(request)

        if candles is None:
            raise LookupError(
                f"No mock candles configured for symbol '{symbol}' "
                f"and timeframe '{timeframe}'"
            )

        return candles[-limit:]