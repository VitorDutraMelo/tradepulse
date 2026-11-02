from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MarketTick:
    """A normalized price update received from a market-data stream."""

    symbol: str
    timestamp: datetime
    price: float
    volume: float | None = None

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if self.price <= 0:
            raise ValueError("price must be greater than zero")

        if self.volume is not None and self.volume < 0:
            raise ValueError("volume cannot be negative")

        object.__setattr__(self, "symbol", normalized_symbol)