"""Candle cache keyed by symbol, timeframe and the latest closed candle.

A cached series is reused only while its newest closed candle is still the
newest candle that *can* be closed (``latest_expected_close``). As soon as a
new boundary passes, the next request goes back to IQ Option. While IQ Option
has not yet published the just-closed candle, re-fetches are paced by
``min_refetch_seconds`` so retries are controlled instead of hammering the
source. The cache never relabels an old series as current: every result
reports whether it is ``CURRENT`` or ``AWAITING_CLOSE_PUBLICATION``.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.domain.candle import Candle
from app.gateway.session import FetchResult, IqSession
from app.gateway.timeframes import candle_close, latest_expected_close


@dataclass(slots=True)
class _Entry:
    fetch: FetchResult
    latest_close: datetime | None
    fetched_monotonic: float


@dataclass(frozen=True, slots=True)
class CacheResult:
    candles: tuple[Candle, ...]
    fetch: FetchResult
    cache_hit: bool
    freshness: str
    expected_close: datetime
    latest_close: datetime | None


class CandleCache:
    def __init__(
        self,
        session: IqSession,
        monotonic: Callable[[], float] = time.monotonic,
        min_refetch_seconds: float = 1.0,
    ) -> None:
        self._session = session
        self._monotonic = monotonic
        self._min_refetch_seconds = min_refetch_seconds
        self._entries: dict[tuple[str, str], _Entry] = {}
        self.hits = 0
        self.misses = 0

    def get(self, symbol: str, timeframe: str, count: int) -> CacheResult:
        key = (symbol.strip().upper(), timeframe)
        # IQ Option returns at most 1000 candles including the open one.
        count = min(count, 999)
        now, _ = self._session.reference_now()
        expected_close = latest_expected_close(now, timeframe)
        entry = self._entries.get(key)

        if entry is not None and len(entry.fetch.candles) >= count:
            is_current = entry.latest_close is not None and entry.latest_close >= expected_close
            recently_fetched = (
                self._monotonic() - entry.fetched_monotonic < self._min_refetch_seconds
            )

            if is_current or recently_fetched:
                self.hits += 1
                return self._result(entry, count, True, expected_close)

        self.misses += 1
        # IQ Option counts the still-open candle inside ``count``; ask for one
        # more so the caller receives ``count`` closed candles.
        request_count = max(count, len(entry.fetch.candles) if entry else 0) + 1
        fetch = self._session.fetch_candles(key[0], timeframe, min(request_count, 1000))
        latest_close = (
            candle_close(fetch.candles[-1].timestamp, timeframe) if fetch.candles else None
        )
        entry = _Entry(fetch=fetch, latest_close=latest_close, fetched_monotonic=self._monotonic())
        self._entries[key] = entry

        return self._result(entry, count, False, expected_close)

    @staticmethod
    def _result(
        entry: _Entry,
        count: int,
        cache_hit: bool,
        expected_close: datetime,
    ) -> CacheResult:
        freshness = (
            "CURRENT"
            if entry.latest_close is not None and entry.latest_close >= expected_close
            else "AWAITING_CLOSE_PUBLICATION"
        )

        return CacheResult(
            candles=entry.fetch.candles[-count:],
            fetch=entry.fetch,
            cache_hit=cache_hit,
            freshness=freshness,
            expected_close=expected_close,
            latest_close=entry.latest_close,
        )

    def clear(self) -> None:
        self._entries.clear()
