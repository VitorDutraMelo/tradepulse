import os
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from math import isfinite
from typing import Protocol

from app.domain.candle import Candle
from app.providers.market_data_provider import MarketDataProvider


class IqOptionClient(Protocol):
    """Minimal read-only contract used from iqoptionapi."""

    def connect(self) -> tuple[bool, str | None]:
        """Authenticate the client."""

    def change_balance(self, balance_type: str) -> object:
        """Select the IQ Option practice account."""

    def get_all_open_time(self) -> object:
        """Return current IQ Option asset availability."""

    def get_candles(
        self,
        active: str,
        interval_seconds: int,
        count: int,
        end_time: int,
    ) -> object:
        """Return historical IQ Option candles."""


class IqOptionMarketDataProvider(MarketDataProvider):
    """Read closed IQ Option DEMO candles through the community iqoptionapi."""

    source = "iq_option_demo"
    venue = "iq"
    _max_candle_limit = 1000
    _timeframe_seconds = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
    }

    def __init__(
        self,
        email: str | None = None,
        password: str | None = None,
        now: Callable[[], datetime] | None = None,
        client_factory: Callable[[str, str], IqOptionClient] | None = None,
    ) -> None:
        self._email = email or os.environ.get("IQ_OPTION_DEMO_EMAIL", "")
        self._password = password or os.environ.get(
            "IQ_OPTION_DEMO_PASSWORD",
            "",
        )
        self._now = now or (lambda: datetime.now(tz=UTC))
        self._client_factory = client_factory or self._default_client_factory

    def get_symbols(self) -> tuple[str, ...]:
        """Return currently open symbols reported by IQ Option."""

        client = self._create_connected_practice_client()
        payload = self._call_get_all_open_time(client)

        if not isinstance(payload, Mapping):
            raise ValueError(
                "IQ Option returned an invalid asset availability response"
            )

        symbols: set[str] = set()

        for category_data in payload.values():
            if not isinstance(category_data, Mapping):
                continue

            for symbol, details in category_data.items():
                if not isinstance(symbol, str) or not isinstance(details, Mapping):
                    continue

                if details.get("open") is True:
                    symbols.add(symbol.strip().upper())

        return tuple(sorted(symbols))

    def _fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> Sequence[Candle]:
        if limit > self._max_candle_limit:
            raise ValueError(
                f"limit must not exceed {self._max_candle_limit} for IQ Option"
            )

        interval_seconds = self._timeframe_seconds.get(timeframe)

        if interval_seconds is None:
            supported_timeframes = ", ".join(self._timeframe_seconds)
            raise ValueError(
                "unsupported IQ Option timeframe; supported values are: "
                f"{supported_timeframes}"
            )

        current_time = self._now_utc()
        iq_symbol = self._to_iq_option_symbol(symbol)
        client = self._create_connected_practice_client()
        payload = self._call_get_candles(
            client=client,
            symbol=iq_symbol,
            interval_seconds=interval_seconds,
            limit=limit,
            end_time=int(current_time.timestamp()),
        )

        if not isinstance(payload, list):
            raise ValueError("IQ Option returned an invalid candle response")

        parsed_candles = [
            self._parse_candle(
                raw_candle=raw_candle,
                interval_seconds=interval_seconds,
            )
            for raw_candle in payload
        ]

        closed_candles = [
            candle
            for candle, close_time in parsed_candles
            if close_time <= current_time
        ]

        return tuple(
            sorted(
                closed_candles,
                key=lambda candle: candle.timestamp,
            )
        )

    def _create_connected_practice_client(self) -> IqOptionClient:
        email = self._email.strip()
        password = self._password.strip()

        if not email or not password:
            raise ValueError(
                "IQ_OPTION_DEMO_EMAIL and IQ_OPTION_DEMO_PASSWORD must be configured"
            )

        try:
            client = self._client_factory(email, password)
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "iqoptionapi is not installed; install the pinned project dependency"
            ) from error
        except Exception as error:
            raise ConnectionError("could not create the IQ Option client") from error

        try:
            connected, reason = client.connect()
        except Exception as error:
            raise ConnectionError("could not connect to IQ Option") from error

        if connected is not True:
            detail = reason.strip() if isinstance(reason, str) else ""
            message = "IQ Option demo authentication failed"

            if detail:
                message = f"{message}: {detail}"

            raise PermissionError(message)

        try:
            selection_result = client.change_balance("PRACTICE")
        except Exception as error:
            raise PermissionError(
                "could not select the IQ Option practice account"
            ) from error

        if selection_result is False:
            raise PermissionError(
                "could not select the IQ Option practice account"
            )

        return client

    @staticmethod
    def _default_client_factory(
        email: str,
        password: str,
    ) -> IqOptionClient:
        from iqoptionapi.stable_api import IQ_Option

        return IQ_Option(email, password)

    @staticmethod
    def _call_get_all_open_time(client: IqOptionClient) -> object:
        try:
            return client.get_all_open_time()
        except Exception as error:
            raise ConnectionError(
                "could not retrieve IQ Option asset availability"
            ) from error

    @staticmethod
    def _call_get_candles(
        client: IqOptionClient,
        symbol: str,
        interval_seconds: int,
        limit: int,
        end_time: int,
    ) -> object:
        try:
            return client.get_candles(
                symbol,
                interval_seconds,
                limit,
                end_time,
            )
        except Exception as error:
            raise ConnectionError("could not retrieve IQ Option candles") from error

    @staticmethod
    def _to_iq_option_symbol(symbol: str) -> str:
        normalized_symbol = symbol.strip().upper().replace("/", "")

        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        return normalized_symbol

    @staticmethod
    def _parse_candle(
        raw_candle: object,
        interval_seconds: int,
    ) -> tuple[Candle, datetime]:
        if not isinstance(raw_candle, Mapping):
            raise ValueError("IQ Option returned an invalid candle")

        try:
            open_timestamp = datetime.fromtimestamp(
                float(raw_candle["from"]),
                tz=UTC,
            )
            close_timestamp = datetime.fromtimestamp(
                float(
                    raw_candle.get(
                        "to",
                        open_timestamp.timestamp() + interval_seconds,
                    )
                ),
                tz=UTC,
            )
            open_price = float(raw_candle["open"])
            high_price = float(raw_candle["max"])
            low_price = float(raw_candle["min"])
            close_price = float(raw_candle["close"])
            volume = float(raw_candle.get("volume", 0))
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError("IQ Option returned an invalid candle") from error

        values = (
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        )

        if not all(isfinite(value) for value in values):
            raise ValueError("IQ Option returned a non-finite candle value")

        if close_timestamp <= open_timestamp:
            raise ValueError("IQ Option returned an invalid candle close timestamp")

        return (
            Candle(
                timestamp=open_timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
            ),
            close_timestamp,
        )

    def _now_utc(self) -> datetime:
        current_time = self._now()

        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("IQ Option clock must return a timezone-aware datetime")

        return current_time.astimezone(UTC)