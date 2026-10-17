from dataclasses import dataclass

from app.domain.signal import Signal
from app.providers.market_data_provider import MarketDataProvider
from app.strategies.ema_crossover_strategy import EmaCrossoverStrategy


@dataclass(slots=True)
class MarketAnalysisService:
    """Coordinates market data retrieval and strategy execution."""

    provider: MarketDataProvider
    strategy: EmaCrossoverStrategy

    def analyze(self, symbol: str, timeframe: str, limit: int) -> Signal:
        """Retrieve candles and return the strategy's standardized signal."""
        candles = self.provider.get_candles(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        return self.strategy.analyze(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
        )