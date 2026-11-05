from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.repositories.iq_option_session_repository import (
    IqOptionSessionRepository,
)
from app.services.one_minute_candle_builder import OneMinuteCandleBuilder
from app.streams.otcharts_iq_option_stream import (
    OtchartsIqOptionStream,
    OtchartsIqOptionStreamEvent,
)


class IqOptionStreamEventSource(Protocol):
    """Contract required from a read-only IQ Option stream source."""

    def iter_events(self, symbol: str) -> Iterator[OtchartsIqOptionStreamEvent]:
        """Yield OTCharts-compatible stream events for one IQ Option symbol."""


@dataclass(frozen=True, slots=True)
class IqOptionStreamCaptureResult:
    """Summary of one completed local IQ Option stream capture session."""

    session_directory: Path
    status: str
    event_count: int
    tick_count: int
    candle_count: int
    finished_at: datetime


class IqOptionStreamCaptureService:
    """Capture IQ Option stream events, closed candles and errors in one session."""

    def __init__(
        self,
        stream: IqOptionStreamEventSource,
        candle_builder: OneMinuteCandleBuilder,
        session_repository: IqOptionSessionRepository,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._stream = stream
        self._candle_builder = candle_builder
        self._session_repository = session_repository
        self._now = now or (lambda: datetime.now(tz=UTC))

    def capture(
        self,
        symbol: str,
        max_events: int | None = None,
    ) -> IqOptionStreamCaptureResult:
        """Capture stream data until it ends or the event limit is reached."""

        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("symbol cannot be empty")

        if normalized_symbol != self._candle_builder.symbol:
            raise ValueError("symbol does not match the candle builder symbol")

        if (
            max_events is not None
            and (isinstance(max_events, bool) or max_events <= 0)
        ):
            raise ValueError("max_events must be greater than zero when provided")

        event_count = 0
        tick_count = 0
        candle_count = 0

        try:
            for stream_event in self._stream.iter_events(normalized_symbol):
                self._session_repository.record_stream_event(stream_event)
                event_count += 1

                if stream_event.event == "tick":
                    tick = OtchartsIqOptionStream.event_to_tick(stream_event)

                    self._session_repository.record_tick(
                        tick,
                        received_at=stream_event.received_at,
                    )
                    tick_count += 1

                    for collected_candle in self._candle_builder.add_tick(tick):
                        self._session_repository.record_candle(collected_candle)
                        candle_count += 1

                if max_events is not None and event_count >= max_events:
                    break

            finished_at = self._now_utc()

            for collected_candle in self._candle_builder.close_current_if_elapsed(
                finished_at
            ):
                self._session_repository.record_candle(collected_candle)
                candle_count += 1

            self._session_repository.close(
                status="completed",
                ended_at=finished_at,
            )

            return IqOptionStreamCaptureResult(
                session_directory=self._session_repository.session_directory,
                status="completed",
                event_count=event_count,
                tick_count=tick_count,
                candle_count=candle_count,
                finished_at=finished_at,
            )
        except Exception as error:
            failed_at = self._now_utc()

            try:
                self._session_repository.record_error(error, failed_at)
            finally:
                self._session_repository.close(
                    status="failed",
                    ended_at=failed_at,
                )

            raise

    def _now_utc(self) -> datetime:
        current_time = self._now()

        if current_time.tzinfo is None or current_time.utcoffset() is None:
            raise ValueError("capture clock must return a timezone-aware datetime")

        return current_time.astimezone(UTC)