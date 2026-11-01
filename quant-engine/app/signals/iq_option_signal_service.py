from dataclasses import dataclass

from app.domain.signal import Signal
from app.domain.trade_signal import (
    MarketCategory,
    SignalPlatform,
    TradeAction,
    TradeSignal,
)


@dataclass(frozen=True, slots=True)
class IqOptionSignalService:
    """Prepare non-executable IQ Option manual-decision signals.

    This service intentionally does not convert LONG to CALL or SHORT to PUT.
    Until a market-specific policy is implemented and validated, every output
    remains WAIT.
    """

    def prepare(
        self,
        analysis: Signal,
        market: MarketCategory,
        data_source: str,
    ) -> TradeSignal:
        """Create a safe WAIT signal from an internal market analysis."""
        return TradeSignal(
            platform=SignalPlatform.IQ_OPTION,
            asset=analysis.symbol,
            market=market,
            timeframe=analysis.timeframe,
            timestamp=analysis.timestamp,
            data_source=data_source,
            analysis_direction=analysis.direction,
            action=TradeAction.WAIT,
            entry_time=None,
            expiration_time=None,
            reasons=(
                *analysis.reasons,
                (
                    "No IQ Option policy is configured for this market and data "
                    "source; manual action remains WAIT."
                ),
            ),
        )