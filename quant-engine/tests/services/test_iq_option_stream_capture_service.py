import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.repositories.iq_option_session_repository import (
    IqOptionSessionRepository,
)
from app.services.iq_option_stream_capture_service import (
    IqOptionStreamCaptureService,
)
from app.services.one_minute_candle_builder import OneMinuteCandleBuilder
from app.streams.otcharts_iq_option_stream import OtchartsIqOptionStreamEvent


class FakeEventSource:
    def __init__(
        self,
        events: list[OtchartsIqOptionStreamEvent],
    ) -> None:
        self.events = events
        self.requested_symbols: list[str] = []

    def iter_events(self, symbol: str) -> Iterator[OtchartsIqOptionStreamEvent]:
        self.requested_symbols.append(symbol)
        yield from self.events


class FailingEventSource:
    def __init__(self, first_event: OtchartsIqOptionStreamEvent) -> None:
        self.first_event = first_event

    def iter_events(self, _: str) -> Iterator[OtchartsIqOptionStreamEvent]:
        yield self.first_event
        raise ConnectionError("OTCharts stream disconnected")


def create_tick_event(
    timestamp: datetime,
    price: float,
) -> OtchartsIqOptionStreamEvent:
    return OtchartsIqOptionStreamEvent(
        event="tick",
        data={
            "symbol": "EURUSD-OTC",
            "time": int(timestamp.timestamp()),
            "price": price,
        },
        received_at=timestamp,
    )


def create_repository(tmp_path: Path) -> IqOptionSessionRepository:
    return IqOptionSessionRepository.create(
        root_directory=tmp_path,
        symbol="EURUSD-OTC",
        started_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        session_id="iq-capture-test",
    )


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_lines(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_captures_events_ticks_and_closed_candles(tmp_path: Path) -> None:
    events = [
        OtchartsIqOptionStreamEvent(
            event="connected",
            data={"symbol": "EURUSD-OTC"},
            received_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        ),
        create_tick_event(
            datetime(2026, 11, 2, 10, 0, 2, tzinfo=UTC),
            1.1000,
        ),
        create_tick_event(
            datetime(2026, 11, 2, 10, 0, 20, tzinfo=UTC),
            1.1010,
        ),
        create_tick_event(
            datetime(2026, 11, 2, 10, 1, 1, tzinfo=UTC),
            1.1005,
        ),
    ]
    stream = FakeEventSource(events)
    repository = create_repository(tmp_path)
    service = IqOptionStreamCaptureService(
        stream=stream,
        candle_builder=OneMinuteCandleBuilder("EURUSD-OTC"),
        session_repository=repository,
        now=lambda: datetime(2026, 11, 2, 10, 2, tzinfo=UTC),
    )

    result = service.capture("EURUSD-OTC")

    manifest = read_json(repository.manifest_path)
    candles = read_json_lines(repository.session_directory / "candles.jsonl")

    assert stream.requested_symbols == ["EURUSD-OTC"]
    assert result.status == "completed"
    assert result.event_count == 4
    assert result.tick_count == 3
    assert result.candle_count == 2
    assert len(candles) == 2
    assert candles[0]["open"] == 1.1000
    assert candles[0]["high"] == 1.1010
    assert candles[0]["close"] == 1.1010
    assert manifest["status"] == "completed"
    assert manifest["eventCount"] == 4
    assert manifest["tickCount"] == 3
    assert manifest["candleCount"] == 2


def test_stops_after_requested_event_limit(tmp_path: Path) -> None:
    events = [
        OtchartsIqOptionStreamEvent(
            event="connected",
            data={"symbol": "EURUSD-OTC"},
            received_at=datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        ),
        create_tick_event(
            datetime(2026, 11, 2, 10, 0, 2, tzinfo=UTC),
            1.1000,
        ),
        create_tick_event(
            datetime(2026, 11, 2, 10, 1, 1, tzinfo=UTC),
            1.1010,
        ),
    ]
    repository = create_repository(tmp_path)
    service = IqOptionStreamCaptureService(
        stream=FakeEventSource(events),
        candle_builder=OneMinuteCandleBuilder("EURUSD-OTC"),
        session_repository=repository,
        now=lambda: datetime(2026, 11, 2, 10, 2, tzinfo=UTC),
    )

    result = service.capture(
        "EURUSD-OTC",
        max_events=2,
    )

    manifest = read_json(repository.manifest_path)

    assert result.event_count == 2
    assert result.tick_count == 1
    assert result.candle_count == 1
    assert manifest["eventCount"] == 2
    assert manifest["tickCount"] == 1
    assert manifest["candleCount"] == 1


def test_stops_when_the_capture_deadline_has_elapsed(tmp_path: Path) -> None:
    events = [
        create_tick_event(
            datetime(2026, 11, 2, 10, 0, 2, tzinfo=UTC),
            1.1000,
        ),
        create_tick_event(
            datetime(2026, 11, 2, 10, 1, 1, tzinfo=UTC),
            1.1010,
        ),
    ]
    clock_values = iter(
        [
            datetime(2026, 11, 2, 10, 0, 59, tzinfo=UTC),
            datetime(2026, 11, 2, 10, 1, tzinfo=UTC),
            datetime(2026, 11, 2, 10, 1, tzinfo=UTC),
        ]
    )
    repository = create_repository(tmp_path)
    service = IqOptionStreamCaptureService(
        stream=FakeEventSource(events),
        candle_builder=OneMinuteCandleBuilder("EURUSD-OTC"),
        session_repository=repository,
        now=lambda: next(clock_values),
    )

    result = service.capture(
        "EURUSD-OTC",
        stop_at=datetime(2026, 11, 2, 10, 1, tzinfo=UTC),
    )

    manifest = read_json(repository.manifest_path)

    assert result.status == "completed"
    assert result.event_count == 1
    assert result.tick_count == 1
    assert result.candle_count == 1
    assert result.finished_at == datetime(
        2026,
        11,
        2,
        10,
        1,
        tzinfo=UTC,
    )
    assert manifest["eventCount"] == 1
    assert manifest["tickCount"] == 1
    assert manifest["candleCount"] == 1


def test_records_error_and_closes_failed_session(tmp_path: Path) -> None:
    first_event = create_tick_event(
        datetime(2026, 11, 2, 10, 0, 2, tzinfo=UTC),
        1.1000,
    )
    repository = create_repository(tmp_path)
    service = IqOptionStreamCaptureService(
        stream=FailingEventSource(first_event),
        candle_builder=OneMinuteCandleBuilder("EURUSD-OTC"),
        session_repository=repository,
        now=lambda: datetime(2026, 11, 2, 10, 1, tzinfo=UTC),
    )

    with pytest.raises(ConnectionError, match="stream disconnected"):
        service.capture("EURUSD-OTC")

    manifest = read_json(repository.manifest_path)
    errors = read_json_lines(repository.session_directory / "errors.jsonl")

    assert manifest["status"] == "failed"
    assert manifest["eventCount"] == 1
    assert manifest["tickCount"] == 1
    assert manifest["errorCount"] == 1
    assert errors[0]["errorType"] == "ConnectionError"
    assert errors[0]["message"] == "OTCharts stream disconnected"


def test_rejects_invalid_capture_configuration(tmp_path: Path) -> None:
    repository = create_repository(tmp_path)
    service = IqOptionStreamCaptureService(
        stream=FakeEventSource([]),
        candle_builder=OneMinuteCandleBuilder("EURUSD-OTC"),
        session_repository=repository,
        now=lambda: datetime(2026, 11, 2, 10, 1, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="does not match"):
        service.capture("GBPUSD-OTC")

    with pytest.raises(ValueError, match="max_events must be greater than zero"):
        service.capture(
            "EURUSD-OTC",
            max_events=0,
        )

    with pytest.raises(ValueError, match="stop_at must be a timezone-aware"):
        service.capture(
            "EURUSD-OTC",
            stop_at=datetime(2026, 11, 2, 10, 1),
        )