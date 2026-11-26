"""MarketDataProvider backed by the shared session and candle cache.

Existing analyses (M1 trend strategy, M5 engine, M15 context) accept an
injectable provider. Passing this provider makes them reuse the single
persistent session instead of logging in on every call, without changing a
single rule of the strategies.
"""

from collections.abc import Sequence

from app.domain.candle import Candle
from app.gateway.candle_cache import CacheResult, CandleCache
from app.gateway.timeframes import candle_close, candle_id, to_iso
from app.providers.market_data_provider import MarketDataProvider


class SessionBackedProvider(MarketDataProvider):
    source = "iq_option_demo"
    venue = "iq"

    def __init__(self, cache: CandleCache) -> None:
        self._cache = cache
        self.fetches: list[CacheResult] = []

    def _fetch_candles(self, symbol: str, timeframe: str, limit: int) -> Sequence[Candle]:
        result = self._cache.get(symbol, timeframe, limit)
        self.fetches.append(result)
        return result.candles

    def fetch_metadata(self) -> list[dict[str, object]]:
        """Observed timing of every candle read performed for one analysis."""

        payload: list[dict[str, object]] = []

        for result in self.fetches:
            fetch = result.fetch
            latest = result.candles[-1] if result.candles else None
            source_close = fetch.source_close_times[-1] if fetch.source_close_times else None

            payload.append(
                {
                    "symbol": fetch.symbol,
                    "timeframe": fetch.timeframe,
                    "cacheHit": result.cache_hit,
                    "freshness": result.freshness,
                    "expectedLatestCloseTime": to_iso(result.expected_close),
                    "receivedClosedCandles": len(result.candles),
                    "latestClosedCandle": (
                        {
                            "candleId": candle_id(fetch.symbol, fetch.timeframe, latest.timestamp),
                            "openTime": to_iso(latest.timestamp),
                            "closeTime": to_iso(candle_close(latest.timestamp, fetch.timeframe)),
                            "closeTimeKind": "DERIVED_OPEN_PLUS_INTERVAL",
                            "sourceCloseTime": to_iso(source_close),
                            "sourceCloseTimeKind": "OBSERVED_SOURCE_FIELD",
                        }
                        if latest is not None
                        else None
                    ),
                    "requestedAt": to_iso(fetch.requested_at),
                    "receivedAt": to_iso(fetch.received_at),
                    "collectionDurationMs": round(
                        (fetch.received_at - fetch.requested_at).total_seconds() * 1000,
                        3,
                    ),
                    "closedCandleClock": fetch.reference_clock,
                    "observedQuote": (
                        fetch.observed_quote.to_payload()
                        if fetch.observed_quote is not None
                        else None
                    ),
                }
            )

        return payload
