import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.candle import Candle
from app.domain.collected_candle import CollectedCandle
from app.domain.market_tick import MarketTick
from app.repositories.iq_option_session_repository import (
    IqOptionSessionRepository,
)
from app.streams.otcharts_iq_option_stream import OtchartsIqOptionStreamEvent


def create_repository(tmp_path: Path) -> IqOptionSessionRepository:
    return IqOptionSessionRepository.create(
        root_directory=tmp_path,
        symbol="EURUSD-OTC",
        started_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
        session_id="iq-20261102-120000-eurusd-otc",
    )


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_lines(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def create_collected_candle() -> CollectedCandle:
    return CollectedCandle(
        candle=Candle(
            timestamp=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
            open=1.1000,
            high=1.1010,
            low=1.0990,
            close=1.1005,
            volume=0.0,
        ),
        tick_count=3,
        volume_available=False,
        source_first_timestamp=datetime(2026, 11, 2, 12, 0, 2, tzinfo=UTC),
        source_last_timestamp=datetime(2026, 11, 2, 12, 0, 50, tzinfo=UTC),
        missing_minutes_after=0,
    )


def test_creates_session_manifest(tmp_path: Path) -> None:
    repository = create_repository(tmp_path)

    manifest = read_json(repository.manifest_path)

    assert repository.session_directory.name == "iq-20261102-120000-eurusd-otc"
    assert manifest == {
        "schemaVersion": 1,
        "sessionId": "iq-20261102-120000-eurusd-otc",
        "symbol": "EURUSD-OTC",
        "venue": "iq",
        "source": "otcharts_iq_option_stream",
        "status": "collecting",
        "startedAt": "2026-11-02T12:00:00+00:00",
        "endedAt": None,
        "eventCount": 0,
        "tickCount": 0,
        "candleCount": 0,
        "errorCount": 0,
        "chartObservationCount": 0,
    }


def test_records_event_tick_candle_and_chart_observation(tmp_path: Path) -> None:
    repository = create_repository(tmp_path)

    stream_event = OtchartsIqOptionStreamEvent(
        event="tick",
        data={
            "symbol": "EURUSD-OTC",
            "time": 1793620802,
            "price": 1.1000,
        },
        received_at=datetime(2026, 11, 2, 12, 0, 3, tzinfo=UTC),
    )
    tick = MarketTick(
        symbol="EURUSD-OTC",
        timestamp=datetime(2026, 11, 2, 12, 0, 2, tzinfo=UTC),
        price=1.1000,
    )

    repository.record_stream_event(stream_event)
    repository.record_tick(
        tick,
        received_at=datetime(2026, 11, 2, 12, 0, 3, tzinfo=UTC),
    )
    repository.record_candle(create_collected_candle())
    repository.record_chart_observation(
        observed_at=datetime(2026, 11, 2, 12, 1, tzinfo=UTC),
        displayed_price=1.1005,
        note="Valor exibido no gráfico IQ.",
    )

    events = read_json_lines(repository.session_directory / "events.jsonl")
    ticks = read_json_lines(repository.session_directory / "ticks.jsonl")
    candles = read_json_lines(repository.session_directory / "candles.jsonl")
    observations = read_json_lines(
        repository.session_directory / "iq-chart-observations.jsonl"
    )
    manifest = read_json(repository.manifest_path)

    assert events[0]["event"] == "tick"
    assert ticks[0]["symbol"] == "EURUSD-OTC"
    assert ticks[0]["price"] == 1.1000
    assert candles[0]["volumeAvailable"] is False
    assert candles[0]["tickCount"] == 3
    assert observations[0]["displayedPrice"] == 1.1005
    assert observations[0]["note"] == "Valor exibido no gráfico IQ."
    assert manifest["eventCount"] == 1
    assert manifest["tickCount"] == 1
    assert manifest["candleCount"] == 1
    assert manifest["chartObservationCount"] == 1


def test_records_redacted_error_and_closes_session(tmp_path: Path) -> None:
    repository = create_repository(tmp_path)

    repository.record_error(
        RuntimeError("OTCharts rejected otc_live_secretvalue"),
        occurred_at=datetime(2026, 11, 2, 12, 5, tzinfo=UTC),
    )
    repository.close(
        status="failed",
        ended_at=datetime(2026, 11, 2, 12, 6, tzinfo=UTC),
    )

    errors = read_json_lines(repository.session_directory / "errors.jsonl")
    manifest = read_json(repository.manifest_path)

    assert errors == [
        {
            "occurredAt": "2026-11-02T12:05:00+00:00",
            "errorType": "RuntimeError",
            "message": "OTCharts rejected [REDACTED_OTCHARTS_KEY]",
        }
    ]
    assert manifest["errorCount"] == 1
    assert manifest["status"] == "failed"
    assert manifest["endedAt"] == "2026-11-02T12:06:00+00:00"


def test_rejects_records_after_session_is_closed(tmp_path: Path) -> None:
    repository = create_repository(tmp_path)

    repository.close(
        status="completed",
        ended_at=datetime(2026, 11, 2, 12, 1, tzinfo=UTC),
    )

    with pytest.raises(RuntimeError, match="already closed"):
        repository.record_chart_observation(
            observed_at=datetime(2026, 11, 2, 12, 2, tzinfo=UTC),
            displayed_price=1.1000,
        )


def test_rejects_unsafe_or_duplicate_session_identifiers(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported characters"):
        IqOptionSessionRepository.create(
            root_directory=tmp_path,
            symbol="EURUSD-OTC",
            started_at=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
            session_id="../outside",
        )

    create_repository(tmp_path)

    with pytest.raises(FileExistsError, match="already exists"):
        create_repository(tmp_path)