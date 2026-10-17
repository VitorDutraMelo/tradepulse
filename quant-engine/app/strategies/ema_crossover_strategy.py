from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.candle import Candle
from app.domain.signal import Signal, SignalDirection
from app.indicators.ema import calculate_close_ema


@dataclass(frozen=True, slots=True)
class EmaCrossoverStrategy:
    """Produce a signal when a fast EMA crosses a slow EMA."""

    fast_period: int = 9
    slow_period: int = 21

    def __post_init__(self) -> None:
        if isinstance(self.fast_period, bool) or isinstance(self.slow_period, bool):
            raise ValueError("periods must be integers")

        if not isinstance(self.fast_period, int) or not isinstance(self.slow_period, int):
            raise ValueError("periods must be integers")

        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("periods must be greater than zero")

        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be smaller than slow_period")

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
    ) -> Signal:
        """Analyze candles and return a standardized EMA crossover signal."""
        if not candles:
            raise ValueError("candles must contain at least one item")

        latest_candle = candles[-1]
        required_candles = self.slow_period + 1

        if len(candles) < required_candles:
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=latest_candle.timestamp,
                direction=SignalDirection.NEUTRAL,
                score=0,
                reasons=(
                    f"Insufficient data: need at least {required_candles} candles "
                    "to detect an EMA crossover",
                ),
            )

        fast_ema = calculate_close_ema(candles, self.fast_period)
        slow_ema = calculate_close_ema(candles, self.slow_period)

        previous_fast_ema = fast_ema[-2]
        current_fast_ema = fast_ema[-1]
        previous_slow_ema = slow_ema[-2]
        current_slow_ema = slow_ema[-1]

        if previous_fast_ema <= previous_slow_ema and current_fast_ema > current_slow_ema:
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=latest_candle.timestamp,
                direction=SignalDirection.LONG,
                score=70,
                reasons=(
                    f"EMA {self.fast_period} crossed above EMA {self.slow_period}",
                ),
            )

        if previous_fast_ema >= previous_slow_ema and current_fast_ema < current_slow_ema:
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=latest_candle.timestamp,
                direction=SignalDirection.SHORT,
                score=70,
                reasons=(
                    f"EMA {self.fast_period} crossed below EMA {self.slow_period}",
                ),
            )

        return Signal(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=latest_candle.timestamp,
            direction=SignalDirection.NEUTRAL,
            score=20,
            reasons=(
                f"No EMA {self.fast_period}/{self.slow_period} crossover detected",
            ),
        )