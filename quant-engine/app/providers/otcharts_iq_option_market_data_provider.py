import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.domain.candle import Candle
from app.providers.market_data_provider import MarketDataProvider


class OtchartsIqOptionMarketDataProvider(MarketDataProvider):
    """Read closed IQ Option candles from the OTCharts read-only data API."""

    source = "otcharts_iq_option"
    venue = "iq"

    _timeframe_seconds = {
        "1m": 60,
        "5m": 300,
        "10m": 600,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://otcharts.com",
        timeout_seconds: float = 10.0,
    ) -> None:
        configured_api_key = api_key or os.environ.get("OTCHARTS_API_KEY", "")

        if not configured_api_key.strip():
            raise ValueError("OTCHARTS_API_KEY is not configured")

        self._api_key = configured_api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def get_symbols(self) -> tuple[str, ...]:
        """Return the current official IQ Option symbol catalogue from OTCharts."""
        payload = self._request_json("/v1/symbols", {"venue": self.venue})

        if not isinstance(payload, dict):
            raise ValueError("OTCharts returned an unexpected symbol response")

        symbols = payload.get("symbols")

        if not isinstance(symbols, list):
            raise ValueError("OTCharts returned an unexpected symbol response")

        result: list[str] = []

        for item in symbols:
            if not isinstance(item, dict):
                raise ValueError("OTCharts returned an invalid symbol")

            symbol = item.get("symbol")

            if not isinstance(symbol, str) or not symbol.strip():
                raise ValueError("OTCharts returned an invalid symbol")

            result.append(symbol)

        return tuple(result)

    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[Candle]:
        timeframe_seconds = self._to_timeframe_seconds(timeframe)

        if limit > 5000:
            raise ValueError("limit must not exceed 5000 for OTCharts")

        normalized_symbol = symbol.strip().upper()
        payload = self._request_json(
            "/v1/candles",
            {
                "venue": self.venue,
                "symbol": normalized_symbol,
                "tf": timeframe_seconds,
                "limit": limit,
            },
        )

        if not isinstance(payload, dict):
            raise ValueError("OTCharts returned an unexpected candle response")

        response_symbol = payload.get("symbol")

        if response_symbol != normalized_symbol:
            raise ValueError("OTCharts returned candles for an unexpected symbol")

        self._validate_gaps(payload.get("gaps"))

        raw_candles = payload.get("candles")

        if not isinstance(raw_candles, list):
            raise ValueError("OTCharts returned an unexpected candle response")

        current_time = datetime.now(tz=UTC)

        return tuple(
            self._parse_candle(raw_candle)
            for raw_candle in raw_candles
            if self._is_candle_closed(
                raw_candle,
                timeframe_seconds=timeframe_seconds,
                current_time=current_time,
            )
        )

    def _request_json(
        self,
        path: str,
        query: dict[str, str | int],
    ) -> object:
        url = f"{self._base_url}{path}?{urlencode(query)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "User-Agent": "TradePulse-QuantEngine/0.1",
            },
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                raise LookupError("OTCharts could not find the requested IQ Option data") from error

            if error.code in (401, 403):
                raise PermissionError(
                    "OTCharts rejected the API key or IQ Option venue access"
                ) from error

            if error.code == 429:
                raise ConnectionError("OTCharts request limit has been reached") from error

            raise ConnectionError(
                f"OTCharts request failed with HTTP status {error.code}"
            ) from error
        except (URLError, OSError) as error:
            raise ConnectionError("could not retrieve candles from OTCharts") from error
        except json.JSONDecodeError as error:
            raise ValueError("OTCharts returned an invalid JSON response") from error

    @classmethod
    def _to_timeframe_seconds(cls, timeframe: str) -> int:
        try:
            return cls._timeframe_seconds[timeframe]
        except KeyError as error:
            supported_timeframes = ", ".join(cls._timeframe_seconds)

            raise ValueError(
                f"timeframe '{timeframe}' is not supported for IQ Option OTCharts data; "
                f"supported values: {supported_timeframes}"
            ) from error

    @staticmethod
    def _validate_gaps(gaps: object) -> None:
        if not isinstance(gaps, dict):
            raise ValueError("OTCharts returned an invalid candle gap response")

        runs = gaps.get("runs")
        missing_bars = gaps.get("missingBars")

        if (
            not isinstance(runs, int)
            or isinstance(runs, bool)
            or not isinstance(missing_bars, int)
            or isinstance(missing_bars, bool)
            or runs < 0
            or missing_bars < 0
        ):
            raise ValueError("OTCharts returned an invalid candle gap response")

        if runs > 0 or missing_bars > 0:
            raise ValueError(
                "OTCharts IQ Option candle response contains missing bars and cannot "
                "be used for analysis"
            )

    @staticmethod
    def _is_candle_closed(
        raw_candle: object,
        timeframe_seconds: int,
        current_time: datetime,
    ) -> bool:
        if not isinstance(raw_candle, dict):
            raise ValueError("OTCharts returned an invalid candle")

        timestamp = raw_candle.get("time")

        if isinstance(timestamp, bool):
            raise ValueError("OTCharts returned an invalid candle")

        try:
            candle_open_time = datetime.fromtimestamp(float(timestamp), tz=UTC)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("OTCharts returned an invalid candle") from error

        return candle_open_time.timestamp() + timeframe_seconds <= current_time.timestamp()

    @staticmethod
    def _parse_candle(raw_candle: object) -> Candle:
        if not isinstance(raw_candle, dict):
            raise ValueError("OTCharts returned an invalid candle")

        try:
            return Candle(
                timestamp=datetime.fromtimestamp(float(raw_candle["time"]), tz=UTC),
                open=float(raw_candle["open"]),
                high=float(raw_candle["high"]),
                low=float(raw_candle["low"]),
                close=float(raw_candle["close"]),
                volume=float(raw_candle["volume"]),
            )
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError("OTCharts returned an invalid candle") from error