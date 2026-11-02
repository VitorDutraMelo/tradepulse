import json
import os
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from math import isfinite
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.domain.market_tick import MarketTick


class OtchartsIqOptionStreamPlanUnavailableError(ConnectionError):
    """Raised when the OTCharts plan cannot access IQ Option streaming."""


class OtchartsIqOptionStreamRateLimitError(ConnectionError):
    """Raised when OTCharts rejects a stream because of rate limits."""


@dataclass(frozen=True, slots=True)
class OtchartsIqOptionStreamEvent:
    """One Server-Sent Event received from the OTCharts IQ Option stream."""

    event: str
    data: dict[str, object]
    received_at: datetime

    def __post_init__(self) -> None:
        if not self.event.strip():
            raise ValueError("event cannot be empty")

        if self.received_at.tzinfo is None or self.received_at.utcoffset() is None:
            raise ValueError("received_at must be timezone-aware")


class OtchartsIqOptionStream:
    """Read-only OTCharts Server-Sent Events client for one IQ Option symbol."""

    venue = "iq"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://otcharts.com",
        timeout_seconds: float = 75.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        configured_api_key = api_key or os.environ.get("OTCHARTS_API_KEY", "")

        if not configured_api_key.strip():
            raise ValueError("OTCHARTS_API_KEY is not configured")

        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        self._api_key = configured_api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._now = now or (lambda: datetime.now(tz=UTC))

    def iter_events(self, symbol: str) -> Iterator[OtchartsIqOptionStreamEvent]:
        """Yield parsed OTCharts stream events for exactly one IQ Option symbol."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        request = Request(
            self._build_stream_url(normalized_symbol),
            headers={
                "Accept": "text/event-stream",
                "Authorization": f"Bearer {self._api_key}",
                "Cache-Control": "no-cache",
                "User-Agent": "TradePulse-QuantEngine/0.1",
            },
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                yield from self._parse_sse_lines(response)
        except HTTPError as error:
            if error.code == 402:
                raise OtchartsIqOptionStreamPlanUnavailableError(
                    "OTCharts IQ Option streaming is unavailable for the current API plan"
                ) from error

            if error.code in (401, 403):
                raise PermissionError(
                    "OTCharts rejected the API key or IQ Option venue access"
                ) from error

            if error.code == 404:
                raise LookupError(
                    "OTCharts could not find the requested IQ Option stream"
                ) from error

            if error.code == 429:
                raise OtchartsIqOptionStreamRateLimitError(
                    "OTCharts stream request limit has been reached"
                ) from error

            raise ConnectionError(
                f"OTCharts stream request failed with HTTP status {error.code}"
            ) from error
        except (URLError, OSError) as error:
            raise ConnectionError(
                "could not connect to the OTCharts IQ Option stream"
            ) from error

    def iter_ticks(self, symbol: str) -> Iterator[MarketTick]:
        """Yield normalized ticks while rejecting ticks for an unexpected symbol."""

        normalized_symbol = symbol.strip().upper()

        for stream_event in self.iter_events(normalized_symbol):
            if stream_event.event != "tick":
                continue

            tick = self.event_to_tick(stream_event)

            if tick.symbol != normalized_symbol:
                raise ValueError(
                    "OTCharts returned a tick for an unexpected IQ Option symbol"
                )

            yield tick

    @staticmethod
    def event_to_tick(stream_event: OtchartsIqOptionStreamEvent) -> MarketTick:
        """Convert an OTCharts tick SSE event into the shared MarketTick model."""

        if stream_event.event != "tick":
            raise ValueError("only tick events can be converted to MarketTick")

        data = stream_event.data

        symbol = data.get("symbol")
        timestamp = data.get("time")
        price = data.get("price")
        volume = data.get("volume")

        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("OTCharts returned an invalid tick symbol")

        if isinstance(timestamp, bool):
            raise ValueError("OTCharts returned an invalid tick timestamp")

        if isinstance(price, bool):
            raise ValueError("OTCharts returned an invalid tick price")

        if isinstance(volume, bool):
            raise ValueError("OTCharts returned an invalid tick volume")

        try:
            source_timestamp = datetime.fromtimestamp(float(timestamp), tz=UTC)
            normalized_price = float(price)
            normalized_volume = float(volume) if volume is not None else None
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("OTCharts returned an invalid tick") from error

        if not isfinite(normalized_price) or normalized_price <= 0:
            raise ValueError("OTCharts returned an invalid tick price")

        if (
            normalized_volume is not None
            and (not isfinite(normalized_volume) or normalized_volume < 0)
        ):
            raise ValueError("OTCharts returned an invalid tick volume")

        return MarketTick(
            symbol=symbol,
            timestamp=source_timestamp,
            price=normalized_price,
            volume=normalized_volume,
        )

    def _build_stream_url(self, symbol: str) -> str:
        query = urlencode(
            {
                "venue": self.venue,
                "symbol": symbol,
            }
        )

        return f"{self._base_url}/v1/stream?{query}"

    def _parse_sse_lines(
        self,
        lines: Iterable[bytes | str],
    ) -> Iterator[OtchartsIqOptionStreamEvent]:
        event_name = "message"
        data_lines: list[str] = []

        for raw_line in lines:
            line = self._decode_line(raw_line)

            if not line:
                stream_event = self._dispatch_event(event_name, data_lines)

                if stream_event is not None:
                    yield stream_event

                event_name = "message"
                data_lines = []
                continue

            if line.startswith(":"):
                continue

            field, separator, value = line.partition(":")

            if not separator:
                continue

            if value.startswith(" "):
                value = value[1:]

            if field == "event":
                event_name = value
            elif field == "data":
                data_lines.append(value)

        stream_event = self._dispatch_event(event_name, data_lines)

        if stream_event is not None:
            yield stream_event

    def _dispatch_event(
        self,
        event_name: str,
        data_lines: list[str],
    ) -> OtchartsIqOptionStreamEvent | None:
        if not data_lines:
            return None

        raw_data = "\n".join(data_lines)

        try:
            parsed_data = json.loads(raw_data)
        except json.JSONDecodeError as error:
            raise ValueError("OTCharts returned invalid stream event JSON") from error

        if not isinstance(parsed_data, dict):
            raise ValueError("OTCharts returned an invalid stream event payload")

        received_at = self._now()

        if received_at.tzinfo is None or received_at.utcoffset() is None:
            raise ValueError("stream clock must return a timezone-aware datetime")

        return OtchartsIqOptionStreamEvent(
            event=event_name,
            data=parsed_data,
            received_at=received_at.astimezone(UTC),
        )

    @staticmethod
    def _decode_line(raw_line: bytes | str) -> str:
        try:
            decoded_line = (
                raw_line.decode("utf-8")
                if isinstance(raw_line, bytes)
                else raw_line
            )
        except UnicodeDecodeError as error:
            raise ValueError("OTCharts returned a non-UTF-8 stream event") from error

        return decoded_line.rstrip("\r\n")