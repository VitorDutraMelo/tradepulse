from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SignalDirection(str, Enum):
    """Possible directional outcomes produced by a strategy."""

    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class Signal:
    """A standardized market-analysis signal produced by a strategy."""

    symbol: str
    timeframe: str
    timestamp: datetime
    direction: SignalDirection
    score: int
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")

        if not self.timeframe.strip():
            raise ValueError("timeframe must not be empty")

        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if not isinstance(self.direction, SignalDirection):
            raise ValueError("direction must be a SignalDirection")

        if isinstance(self.score, bool) or not isinstance(self.score, int):
            raise ValueError("score must be an integer")

        if not 0 <= self.score <= 100:
            raise ValueError("score must be between 0 and 100")

        if not self.reasons:
            raise ValueError("reasons must contain at least one item")

        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("reasons must not contain empty items")