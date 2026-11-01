from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.signal import SignalDirection


class MarketCategory(str, Enum):
    """Market categories supported by the product signal layer."""

    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    INDEX = "INDEX"
    COMMODITY = "COMMODITY"
    OTC = "OTC"


class TradeAction(str, Enum):
    """Manual platform actions considered by a product-level signal."""

    CALL = "CALL"
    PUT = "PUT"
    WAIT = "WAIT"


class SignalPlatform(str, Enum):
    """Platforms for which a product-level signal may be prepared."""

    IQ_OPTION = "IQ_OPTION"


@dataclass(frozen=True, slots=True)
class TradeSignal:
    """A manual, platform-oriented signal distinct from market analysis."""

    platform: SignalPlatform
    asset: str
    market: MarketCategory
    timeframe: str
    timestamp: datetime
    data_source: str
    analysis_direction: SignalDirection
    action: TradeAction
    entry_time: datetime | None
    expiration_time: datetime | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.platform, SignalPlatform):
            raise ValueError("platform must be a SignalPlatform")

        if not self.asset.strip():
            raise ValueError("asset must not be empty")

        if not isinstance(self.market, MarketCategory):
            raise ValueError("market must be a MarketCategory")

        if not self.timeframe.strip():
            raise ValueError("timeframe must not be empty")

        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        if not self.data_source.strip():
            raise ValueError("data_source must not be empty")

        if not isinstance(self.analysis_direction, SignalDirection):
            raise ValueError("analysis_direction must be a SignalDirection")

        if not isinstance(self.action, TradeAction):
            raise ValueError("action must be a TradeAction")

        if not self.reasons:
            raise ValueError("reasons must contain at least one item")

        if any(not reason.strip() for reason in self.reasons):
            raise ValueError("reasons must not contain empty items")

        if self.action is TradeAction.WAIT:
            if self.entry_time is not None or self.expiration_time is not None:
                raise ValueError("WAIT signals must not define entry or expiration times")
            return

        if self.entry_time is None or self.expiration_time is None:
            raise ValueError("CALL and PUT signals require entry and expiration times")

        if (
            self.entry_time.tzinfo is None
            or self.entry_time.utcoffset() is None
            or self.expiration_time.tzinfo is None
            or self.expiration_time.utcoffset() is None
        ):
            raise ValueError("entry and expiration times must be timezone-aware")

        if self.entry_time < self.timestamp:
            raise ValueError("entry_time must not be before timestamp")

        if self.expiration_time <= self.entry_time:
            raise ValueError("expiration_time must be after entry_time")