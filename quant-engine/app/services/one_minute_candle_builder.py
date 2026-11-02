from datetime import UTC, datetime, timedelta

from app.domain.candle import Candle
from app.domain.collected_candle import CollectedCandle
from app.domain.market_tick import MarketTick


class OneMinuteCandleBuilder:
    """Build closed UTC one-minute candles from chronological market ticks."""

    _candle_duration = timedelta(minutes=1)

    def __init__(self, symbol: str) -> None:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        self._symbol = normalized_symbol
        self._current_minute_start: datetime | None = None
        self._ticks: list[MarketTick] = []
        self._last_tick_timestamp: datetime | None = None

    @property
    def symbol(self) -> str:
        return self._symbol

    def add_tick(self, tick: MarketTick) -> tuple[CollectedCandle, ...]:
        """Add one tick and return any candle closed by a minute rollover."""

        if tick.symbol != self._symbol:
            raise ValueError(
                f"tick symbol '{tick.symbol}' does not match builder symbol "
                f"'{self._symbol}'"
            )

        tick_timestamp = tick.timestamp.astimezone(UTC)

        if (
            self._last_tick_timestamp is not None
            and tick_timestamp <= self._last_tick_timestamp
        ):
            raise ValueError(
                "stream ticks must be strictly chronological; duplicate or "
                "out-of-order tick detected"
            )

        minute_start = self._minute_start(tick_timestamp)

        if self._current_minute_start is None:
            self._start_minute(minute_start, tick)
            return ()

        if minute_start == self._current_minute_start:
            self._ticks.append(tick)
            self._last_tick_timestamp = tick_timestamp
            return ()

        missing_minutes_after = self._missing_minutes_between(
            self._current_minute_start,
            minute_start,
        )
        closed_candle = self._build_current_candle(missing_minutes_after)

        self._start_minute(minute_start, tick)

        return (closed_candle,)

    def close_current_if_elapsed(
        self,
        reference_time: datetime,
    ) -> tuple[CollectedCandle, ...]:
        """Close the active candle only after its full minute has elapsed."""

        if reference_time.tzinfo is None or reference_time.utcoffset() is None:
            raise ValueError("reference_time must be timezone-aware")

        if self._current_minute_start is None:
            return ()

        reference_time_utc = reference_time.astimezone(UTC)
        minute_end = self._current_minute_start + self._candle_duration

        if reference_time_utc < minute_end:
            return ()

        closed_candle = self._build_current_candle(missing_minutes_after=0)
        self._current_minute_start = None
        self._ticks = []
        self._last_tick_timestamp = None

        return (closed_candle,)

    @staticmethod
    def _minute_start(timestamp: datetime) -> datetime:
        return timestamp.replace(second=0, microsecond=0)

    @staticmethod
    def _missing_minutes_between(
        current_minute_start: datetime,
        next_minute_start: datetime,
    ) -> int:
        difference_seconds = (
            next_minute_start - current_minute_start
        ).total_seconds()
        complete_minutes = int(difference_seconds // 60)

        return max(0, complete_minutes - 1)

    def _start_minute(
        self,
        minute_start: datetime,
        tick: MarketTick,
    ) -> None:
        self._current_minute_start = minute_start
        self._ticks = [tick]
        self._last_tick_timestamp = tick.timestamp.astimezone(UTC)

    def _build_current_candle(
        self,
        missing_minutes_after: int,
    ) -> CollectedCandle:
        if self._current_minute_start is None or not self._ticks:
            raise RuntimeError("cannot build a candle without collected ticks")

        prices = [tick.price for tick in self._ticks]
        tick_volumes = [tick.volume for tick in self._ticks]
        volume_available = all(volume is not None for volume in tick_volumes)

        volume = (
            sum(volume for volume in tick_volumes if volume is not None)
            if volume_available
            else 0.0
        )

        candle = Candle(
            timestamp=self._current_minute_start,
            open=prices[0],
            high=max(prices),
            low=min(prices),
            close=prices[-1],
            volume=volume,
        )

        timestamps = [tick.timestamp.astimezone(UTC) for tick in self._ticks]

        return CollectedCandle(
            candle=candle,
            tick_count=len(self._ticks),
            volume_available=volume_available,
            source_first_timestamp=min(timestamps),
            source_last_timestamp=max(timestamps),
            missing_minutes_after=missing_minutes_after,
        )