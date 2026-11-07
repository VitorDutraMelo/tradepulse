from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.candle import Candle
from app.domain.signal import Signal, SignalDirection
from app.indicators.ema import calculate_close_ema
from app.indicators.rsi import calculate_close_rsi


@dataclass(frozen=True, slots=True)
class EmaCrossoverStrategy:
    """Produce EMA crossover signals with an optional RSI confirmation."""

    fast_period: int = 9
    slow_period: int = 21
    rsi_period: int | None = None

    def __post_init__(self) -> None:
        if isinstance(self.fast_period, bool) or isinstance(
            self.slow_period,
            bool,
        ):
            raise ValueError("periods must be integers")

        if not isinstance(self.fast_period, int) or not isinstance(
            self.slow_period,
            int,
        ):
            raise ValueError("periods must be integers")

        if self.fast_period <= 0 or self.slow_period <= 0:
            raise ValueError("periods must be greater than zero")

        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be smaller than slow_period")

        if self.rsi_period is not None:
            if isinstance(self.rsi_period, bool) or not isinstance(
                self.rsi_period,
                int,
            ):
                raise ValueError("rsi_period must be an integer")

            if self.rsi_period <= 0:
                raise ValueError("rsi_period must be greater than zero")

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
    ) -> Signal:
        """Analyze chronological candles and return a standardized signal."""
        if not candles:
            raise ValueError("candles must contain at least one item")

        latest_candle = candles[-1]
        required_candles = self._required_candles()

        if len(candles) < required_candles:
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=latest_candle.timestamp,
                direction=SignalDirection.NEUTRAL,
                score=0,
                reasons=(
                    f"Insufficient data: need at least {required_candles} "
                    "candles to detect an EMA crossover",
                ),
            )

        fast_ema = calculate_close_ema(candles, self.fast_period)
        slow_ema = calculate_close_ema(candles, self.slow_period)

        previous_fast_ema = fast_ema[-2]
        current_fast_ema = fast_ema[-1]
        previous_slow_ema = slow_ema[-2]
        current_slow_ema = slow_ema[-1]

        if (
            previous_fast_ema <= previous_slow_ema
            and current_fast_ema > current_slow_ema
        ):
            return self._build_crossover_signal(
                symbol=symbol,
                timeframe=timeframe,
                candle=latest_candle,
                candles=candles,
                direction=SignalDirection.LONG,
            )

        if (
            previous_fast_ema >= previous_slow_ema
            and current_fast_ema < current_slow_ema
        ):
            return self._build_crossover_signal(
                symbol=symbol,
                timeframe=timeframe,
                candle=latest_candle,
                candles=candles,
                direction=SignalDirection.SHORT,
            )

        if self.rsi_period is not None:
            current_rsi = calculate_close_rsi(candles, self.rsi_period)[-1]

            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=latest_candle.timestamp,
                direction=SignalDirection.NEUTRAL,
                score=20,
                reasons=(
                    (
                        f"No EMA {self.fast_period}/{self.slow_period} "
                        f"crossover detected; current RSI {self.rsi_period} "
                        f"is {current_rsi:.2f}"
                    ),
                ),
            )

        return Signal(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=latest_candle.timestamp,
            direction=SignalDirection.NEUTRAL,
            score=20,
            reasons=(
                f"No EMA {self.fast_period}/{self.slow_period} "
                "crossover detected",
            ),
        )

    def _required_candles(self) -> int:
        ema_required_candles = self.slow_period + 1

        if self.rsi_period is None:
            return ema_required_candles

        return max(ema_required_candles, self.rsi_period + 1)

    def _build_crossover_signal(
        self,
        symbol: str,
        timeframe: str,
        candle: Candle,
        candles: Sequence[Candle],
        direction: SignalDirection,
    ) -> Signal:
        crossover_reason = self._crossover_reason(direction)

        if self.rsi_period is None:
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=candle.timestamp,
                direction=direction,
                score=70,
                reasons=(crossover_reason,),
            )

        current_rsi = calculate_close_rsi(candles, self.rsi_period)[-1]
        minimum_rsi, maximum_rsi, momentum = self._rsi_confirmation_range(
            direction
        )

        if minimum_rsi <= current_rsi <= maximum_rsi:
            return Signal(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=candle.timestamp,
                direction=direction,
                score=70,
                reasons=(
                    crossover_reason,
                    (
                        f"RSI {self.rsi_period} confirms {momentum} "
                        f"momentum ({current_rsi:.2f})"
                    ),
                ),
            )

        return Signal(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=candle.timestamp,
            direction=SignalDirection.NEUTRAL,
            score=20,
            reasons=(
                (
                    f"{crossover_reason} but RSI {self.rsi_period} is "
                    f"{current_rsi:.2f}; expected {minimum_rsi:.2f} to "
                    f"{maximum_rsi:.2f} for confirmation"
                ),
            ),
        )

    def _crossover_reason(self, direction: SignalDirection) -> str:
        if direction is SignalDirection.LONG:
            return (
                f"EMA {self.fast_period} crossed above "
                f"EMA {self.slow_period}"
            )

        return (
            f"EMA {self.fast_period} crossed below "
            f"EMA {self.slow_period}"
        )

    def _rsi_confirmation_range(
        self,
        direction: SignalDirection,
    ) -> tuple[float, float, str]:
        if direction is SignalDirection.LONG:
            return (50.0, 70.0, "upward")

        return (30.0, 50.0, "downward")

