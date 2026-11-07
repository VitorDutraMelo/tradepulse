from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.domain.candle import Candle
from app.domain.iq_option_binary_signal import IqOptionBinarySignal
from app.domain.trade_signal import TradeAction
from app.indicators.adx import calculate_adx
from app.indicators.atr import calculate_atr
from app.indicators.ema import calculate_close_ema
from app.indicators.rsi import calculate_close_rsi


@dataclass(frozen=True, slots=True)
class IqOptionTrendStrategy:
    """Build IQ Option DEMO technical reference scenarios from closed candles.

    Initial thresholds are configurable technical filters only. They are not
    validated as profitable settings and must not be interpreted as a promise
    of a CALL/PUT result.
    """

    fast_ema_period: int = 9
    slow_ema_period: int = 21
    rsi_period: int = 14
    adx_period: int = 14
    atr_period: int = 14
    minimum_adx: float = 20.0
    minimum_ema_atr_ratio: float = 0.15
    call_rsi_minimum: float = 52.0
    call_rsi_maximum: float = 68.0
    put_rsi_minimum: float = 32.0
    put_rsi_maximum: float = 48.0
    max_candle_age_seconds: int = 120
    expiry_candles: int = 1

    _timeframe_seconds = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
    }

    def __post_init__(self) -> None:
        integer_values = {
            "fast_ema_period": self.fast_ema_period,
            "slow_ema_period": self.slow_ema_period,
            "rsi_period": self.rsi_period,
            "adx_period": self.adx_period,
            "atr_period": self.atr_period,
            "max_candle_age_seconds": self.max_candle_age_seconds,
            "expiry_candles": self.expiry_candles,
        }

        for name, value in integer_values.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")

            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")

        if self.fast_ema_period >= self.slow_ema_period:
            raise ValueError(
                "fast_ema_period must be smaller than slow_ema_period"
            )

        numeric_values = {
            "minimum_adx": self.minimum_adx,
            "minimum_ema_atr_ratio": self.minimum_ema_atr_ratio,
            "call_rsi_minimum": self.call_rsi_minimum,
            "call_rsi_maximum": self.call_rsi_maximum,
            "put_rsi_minimum": self.put_rsi_minimum,
            "put_rsi_maximum": self.put_rsi_maximum,
        }

        for name, value in numeric_values.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a number")

        if self.minimum_adx < 0:
            raise ValueError("minimum_adx must not be negative")

        if self.minimum_ema_atr_ratio < 0:
            raise ValueError("minimum_ema_atr_ratio must not be negative")

        if not 0 <= self.call_rsi_minimum <= self.call_rsi_maximum <= 100:
            raise ValueError("CALL RSI range must be between zero and 100")

        if not 0 <= self.put_rsi_minimum <= self.put_rsi_maximum <= 100:
            raise ValueError("PUT RSI range must be between zero and 100")

    def analyze(
        self,
        symbol: str,
        timeframe: str,
        candles: Sequence[Candle],
        source: str,
        analysis_at: datetime | None = None,
    ) -> IqOptionBinarySignal:
        """Return a technical CALL, PUT or WAIT reference from closed candles."""
        normalized_timeframe = timeframe.strip()
        timeframe_seconds = self._timeframe_seconds.get(normalized_timeframe)

        if timeframe_seconds is None:
            supported = ", ".join(self._timeframe_seconds)
            raise ValueError(
                f"unsupported IQ Option timeframe; supported values are: {supported}"
            )

        current_time = self._normalize_time(analysis_at or datetime.now(tz=UTC))

        if not candles:
            return self._wait(
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                reasons=("Insufficient data: no closed IQ Option candles received.",),
            )

        latest_candle = candles[-1]
        last_candle_close_time = latest_candle.timestamp + timedelta(
            seconds=timeframe_seconds
        )
        candle_age_seconds = max(
            0.0,
            (current_time - last_candle_close_time).total_seconds(),
        )
        entry_time = self._next_reference_entry_time(
            current_time,
            timeframe_seconds,
        )
        expiration_time = entry_time + timedelta(
            seconds=timeframe_seconds * self.expiry_candles
        )

        if len(candles) < self.required_candles:
            return self._wait(
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                latest_candle=latest_candle,
                last_candle_close_time=last_candle_close_time,
                candle_age_seconds=candle_age_seconds,
                reference_entry_time=entry_time,
                reference_expiration_time=expiration_time,
                reasons=(
                    (
                        "Insufficient data: need at least "
                        f"{self.required_candles} closed candles for "
                        f"EMA {self.fast_ema_period}/{self.slow_ema_period}, "
                        f"RSI {self.rsi_period}, ADX {self.adx_period} and "
                        f"ATR {self.atr_period}."
                    ),
                ),
            )

        fast_ema = calculate_close_ema(candles, self.fast_ema_period)[-1]
        slow_ema = calculate_close_ema(candles, self.slow_ema_period)[-1]
        rsi = calculate_close_rsi(candles, self.rsi_period)[-1]
        adx = calculate_adx(candles, self.adx_period)[-1]
        atr = calculate_atr(candles, self.atr_period)[-1]
        ema_atr_ratio = abs(fast_ema - slow_ema) / atr if atr > 0 else 0.0

        context = {
            "latest_candle": latest_candle,
            "last_candle_close_time": last_candle_close_time,
            "candle_age_seconds": candle_age_seconds,
            "reference_entry_time": entry_time,
            "reference_expiration_time": expiration_time,
            "ema_fast": fast_ema,
            "ema_slow": slow_ema,
            "rsi": rsi,
            "adx": adx,
            "atr": atr,
        }

        if candle_age_seconds > self.max_candle_age_seconds:
            return self._wait(
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                **context,
                reasons=(
                    (
                        f"Latest closed candle is {candle_age_seconds:.0f}s old; "
                        f"maximum allowed age is {self.max_candle_age_seconds}s."
                    ),
                ),
            )

        if ema_atr_ratio < self.minimum_ema_atr_ratio:
            return self._wait(
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                **context,
                reasons=(
                    (
                        f"EMA {self.fast_ema_period} and EMA "
                        f"{self.slow_ema_period} are too close "
                        f"({ema_atr_ratio:.3f} ATR; minimum "
                        f"{self.minimum_ema_atr_ratio:.3f} ATR)."
                    ),
                ),
            )

        if adx < self.minimum_adx:
            return self._wait(
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                **context,
                reasons=(
                    (
                        f"ADX {self.adx_period} is {adx:.2f}; minimum "
                        f"trend-strength filter is {self.minimum_adx:.2f}."
                    ),
                ),
            )

        if fast_ema > slow_ema:
            if not self.call_rsi_minimum <= rsi <= self.call_rsi_maximum:
                return self._wait(
                    symbol=symbol,
                    timeframe=normalized_timeframe,
                    source=source,
                    analysis_at=current_time,
                    **context,
                    reasons=(
                        (
                            f"Upward EMA trend detected, but RSI {self.rsi_period} "
                            f"is {rsi:.2f}; CALL reference range is "
                            f"{self.call_rsi_minimum:.2f} to "
                            f"{self.call_rsi_maximum:.2f}."
                        ),
                    ),
                )

            return self._signal(
                action=TradeAction.CALL,
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                **context,
                reasons=(
                    (
                        f"EMA {self.fast_ema_period} ({fast_ema:.6f}) is above "
                        f"EMA {self.slow_ema_period} ({slow_ema:.6f})."
                    ),
                    (
                        f"RSI {self.rsi_period} ({rsi:.2f}) is inside the "
                        "configured CALL momentum range."
                    ),
                    (
                        f"ADX {self.adx_period} ({adx:.2f}) confirms the "
                        "configured minimum trend strength."
                    ),
                ),
            )

        if not self.put_rsi_minimum <= rsi <= self.put_rsi_maximum:
            return self._wait(
                symbol=symbol,
                timeframe=normalized_timeframe,
                source=source,
                analysis_at=current_time,
                **context,
                reasons=(
                    (
                        f"Downward EMA trend detected, but RSI {self.rsi_period} "
                        f"is {rsi:.2f}; PUT reference range is "
                        f"{self.put_rsi_minimum:.2f} to "
                        f"{self.put_rsi_maximum:.2f}."
                    ),
                ),
            )

        return self._signal(
            action=TradeAction.PUT,
            symbol=symbol,
            timeframe=normalized_timeframe,
            source=source,
            analysis_at=current_time,
            **context,
            reasons=(
                (
                    f"EMA {self.fast_ema_period} ({fast_ema:.6f}) is below "
                    f"EMA {self.slow_ema_period} ({slow_ema:.6f})."
                ),
                (
                    f"RSI {self.rsi_period} ({rsi:.2f}) is inside the "
                    "configured PUT momentum range."
                ),
                (
                    f"ADX {self.adx_period} ({adx:.2f}) confirms the "
                    "configured minimum trend strength."
                ),
            ),
        )

    @property
    def required_candles(self) -> int:
        return max(
            self.slow_ema_period,
            self.rsi_period + 1,
            self.atr_period + 1,
            (self.adx_period * 2) + 1,
        )

    @staticmethod
    def _next_reference_entry_time(
        current_time: datetime,
        timeframe_seconds: int,
    ) -> datetime:
        current_timestamp = int(current_time.timestamp())
        next_timestamp = (
            (current_timestamp // timeframe_seconds) + 1
        ) * timeframe_seconds

        return datetime.fromtimestamp(next_timestamp, tz=UTC)

    @staticmethod
    def _normalize_time(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("analysis_at must be timezone-aware")

        return value.astimezone(UTC)

    def _wait(
        self,
        symbol: str,
        timeframe: str,
        source: str,
        analysis_at: datetime,
        reasons: tuple[str, ...],
        latest_candle: Candle | None = None,
        last_candle_close_time: datetime | None = None,
        candle_age_seconds: float | None = None,
        reference_entry_time: datetime | None = None,
        reference_expiration_time: datetime | None = None,
        ema_fast: float | None = None,
        ema_slow: float | None = None,
        rsi: float | None = None,
        adx: float | None = None,
        atr: float | None = None,
    ) -> IqOptionBinarySignal:
        return IqOptionBinarySignal(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            analysis_at=analysis_at,
            last_candle_open_time=(
                latest_candle.timestamp if latest_candle is not None else None
            ),
            last_candle_close_time=last_candle_close_time,
            last_candle_age_seconds=candle_age_seconds,
            reference_price=(
                latest_candle.close if latest_candle is not None else None
            ),
            reference_entry_time=reference_entry_time,
            reference_expiration_time=reference_expiration_time,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            adx=adx,
            atr=atr,
            action=TradeAction.WAIT,
            reasons=reasons,
        )

    @staticmethod
    def _signal(
        action: TradeAction,
        symbol: str,
        timeframe: str,
        source: str,
        analysis_at: datetime,
        latest_candle: Candle,
        last_candle_close_time: datetime,
        candle_age_seconds: float,
        reference_entry_time: datetime,
        reference_expiration_time: datetime,
        ema_fast: float,
        ema_slow: float,
        rsi: float,
        adx: float,
        atr: float,
        reasons: tuple[str, ...],
    ) -> IqOptionBinarySignal:
        return IqOptionBinarySignal(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            analysis_at=analysis_at,
            last_candle_open_time=latest_candle.timestamp,
            last_candle_close_time=last_candle_close_time,
            last_candle_age_seconds=candle_age_seconds,
            reference_price=latest_candle.close,
            reference_entry_time=reference_entry_time,
            reference_expiration_time=reference_expiration_time,
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            rsi=rsi,
            adx=adx,
            atr=atr,
            action=action,
            reasons=reasons,
        )