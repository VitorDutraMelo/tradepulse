from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Candle:
    """Normalized OHLCV candle used across every market data provider."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if self.open <= 0:
            raise ValueError("open must be greater than zero")

        if self.high <= 0:
            raise ValueError("high must be greater than zero")

        if self.low <= 0:
            raise ValueError("low must be greater than zero")

        if self.close <= 0:
            raise ValueError("close must be greater than zero")

        if self.volume < 0:
            raise ValueError("volume cannot be negative")

        if self.high < self.low:
            raise ValueError("high cannot be lower than low")

        if self.high < max(self.open, self.close):
            raise ValueError("high must be greater than or equal to open and close")

        if self.low > min(self.open, self.close):
            raise ValueError("low must be lower than or equal to open and close")