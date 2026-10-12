from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.domain.candle import Candle


class MarketDataProvider(ABC):
    """Contract for providers that return normalized OHLCV candles."""

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> tuple[Candle, ...]:
        self._validate_request(symbol=symbol, timeframe=timeframe, limit=limit)

        candles = tuple(
            self._fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
        )

        self._validate_candle_order(candles)

        return candles

    @abstractmethod
    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[Candle]:
        """Fetch normalized candles from a specific provider."""

    @staticmethod
    def _validate_request(
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> None:
        if not symbol.strip():
            raise ValueError("symbol cannot be empty")

        if not timeframe.strip():
            raise ValueError("timeframe cannot be empty")

        if limit <= 0:
            raise ValueError("limit must be greater than zero")

    @staticmethod
    def _validate_candle_order(candles: Sequence[Candle]) -> None:
        for previous, current in zip(candles, candles[1:], strict=False):
            if current.timestamp <= previous.timestamp:
                raise ValueError(
                    "candles must be returned in strictly chronological order"
                )