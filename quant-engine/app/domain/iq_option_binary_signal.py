from dataclasses import dataclass
from datetime import datetime

from app.domain.trade_signal import TradeAction


@dataclass(frozen=True, slots=True)
class IqOptionBinarySignal:
    """Read-only technical reference for an IQ Option DEMO binary scenario.

    This is not an order, a broker settlement, a profit forecast, or a
    probability of success.
    """

    symbol: str
    timeframe: str
    source: str
    analysis_at: datetime
    last_candle_open_time: datetime | None
    last_candle_close_time: datetime | None
    last_candle_age_seconds: float | None
    reference_price: float | None
    reference_entry_time: datetime | None
    reference_expiration_time: datetime | None
    ema_fast: float | None
    ema_slow: float | None
    rsi: float | None
    adx: float | None
    atr: float | None
    action: TradeAction
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.timeframe.strip():
            raise ValueError("timeframe must not be empty")

        if not self.source.strip():
            raise ValueError("source must not be empty")

        if (
            self.analysis_at.tzinfo is None
            or self.analysis_at.utcoffset() is None
        ):
            raise ValueError("analysis_at must be timezone-aware")

        if not isinstance(self.action, TradeAction):
            raise ValueError("action must be a TradeAction")

        if not self.reasons:
            raise ValueError("reasons must contain at least one item")

        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("reasons must not contain empty items")

        if self.last_candle_age_seconds is not None:
            if self.last_candle_age_seconds < 0:
                raise ValueError(
                    "last_candle_age_seconds must not be negative"
                )

        if self.action is TradeAction.WAIT:
            return

        if self.reference_price is None:
            raise ValueError(
                "CALL and PUT signals require a reference_price"
            )

        if (
            self.reference_entry_time is None
            or self.reference_expiration_time is None
        ):
            raise ValueError(
                "CALL and PUT signals require reference entry and expiration times"
            )

        if (
            self.reference_entry_time.tzinfo is None
            or self.reference_entry_time.utcoffset() is None
            or self.reference_expiration_time.tzinfo is None
            or self.reference_expiration_time.utcoffset() is None
        ):
            raise ValueError(
                "reference entry and expiration times must be timezone-aware"
            )

        if self.reference_expiration_time <= self.reference_entry_time:
            raise ValueError(
                "reference_expiration_time must be after reference_entry_time"
            )