from dataclasses import dataclass
from datetime import datetime

from app.domain.candle import Candle


@dataclass(frozen=True, slots=True)
class CollectedCandle:
    """A closed candle built from IQ Option stream ticks.

    When volume_available is false, candle.volume is zero only because the
    provider did not supply volume for every tick. It must not be interpreted
    as confirmed market volume.
    """

    candle: Candle
    tick_count: int
    volume_available: bool
    source_first_timestamp: datetime
    source_last_timestamp: datetime
    missing_minutes_after: int = 0

    def __post_init__(self) -> None:
        if self.tick_count <= 0:
            raise ValueError("tick_count must be greater than zero")

        if (
            self.source_first_timestamp.tzinfo is None
            or self.source_first_timestamp.utcoffset() is None
        ):
            raise ValueError("source_first_timestamp must be timezone-aware")

        if (
            self.source_last_timestamp.tzinfo is None
            or self.source_last_timestamp.utcoffset() is None
        ):
            raise ValueError("source_last_timestamp must be timezone-aware")

        if self.source_last_timestamp < self.source_first_timestamp:
            raise ValueError(
                "source_last_timestamp cannot be earlier than source_first_timestamp"
            )

        if self.missing_minutes_after < 0:
            raise ValueError("missing_minutes_after cannot be negative")