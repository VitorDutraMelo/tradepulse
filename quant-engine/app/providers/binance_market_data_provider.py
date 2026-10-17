import json
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from app.domain.candle import Candle
from app.providers.market_data_provider import MarketDataProvider


class BinanceMarketDataProvider(MarketDataProvider):
    """Read closed public OHLCV candles from Binance Spot market data."""

    def __init__(
        self,
        base_url: str = "https://data-api.binance.vision",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[Candle]:
        if limit > 1000:
            raise ValueError("limit must not exceed 1000 for Binance")

        query = urlencode(
            {
                "symbol": self._to_binance_symbol(symbol),
                "interval": timeframe,
                "limit": limit,
            },
        )
        url = f"{self._base_url}/api/v3/klines?{query}"

        try:
            with urlopen(url, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError) as error:
            raise ConnectionError("could not retrieve candles from Binance") from error
        except json.JSONDecodeError as error:
            raise ValueError("Binance returned an invalid JSON response") from error

        if not isinstance(payload, list):
            raise ValueError("Binance returned an unexpected candle response")

        current_time = datetime.now(tz=UTC)

        return tuple(
            self._parse_candle(kline)
            for kline in payload
            if self._is_candle_closed(kline, current_time)
        )

    @staticmethod
    def _to_binance_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper().replace("-", "")

        if normalized_symbol.endswith("USD") and not normalized_symbol.endswith("USDT"):
            return f"{normalized_symbol[:-3]}USDT"

        return normalized_symbol

    @staticmethod
    def _is_candle_closed(kline: object, current_time: datetime) -> bool:
        if not isinstance(kline, list) or len(kline) < 7:
            raise ValueError("Binance returned an invalid candle")

        try:
            close_time = datetime.fromtimestamp(float(kline[6]) / 1000, tz=UTC)
        except (TypeError, ValueError) as error:
            raise ValueError("Binance returned an invalid candle") from error

        return close_time <= current_time

    @staticmethod
    def _parse_candle(kline: object) -> Candle:
        if not isinstance(kline, list) or len(kline) < 7:
            raise ValueError("Binance returned an invalid candle")

        try:
            return Candle(
                timestamp=datetime.fromtimestamp(float(kline[0]) / 1000, tz=UTC),
                open=float(kline[1]),
                high=float(kline[2]),
                low=float(kline[3]),
                close=float(kline[4]),
                volume=float(kline[5]),
            )
        except (TypeError, ValueError) as error:
            raise ValueError("Binance returned an invalid candle") from error
