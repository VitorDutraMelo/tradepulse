import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.domain.candle import Candle
from app.domain.signal import Signal, SignalDirection
from app.repositories.iq_option_demo_analysis_repository import (
    IqOptionDemoAnalysisRepository,
)


def create_signal() -> Signal:
    return Signal(
        symbol="EURUSD-OTC",
        timeframe="1m",
        timestamp=datetime(2026, 11, 7, 9, 14, tzinfo=UTC),
        direction=SignalDirection.NEUTRAL,
        score=20,
        reasons=("No EMA 9/21 crossover detected",),
    )


def create_candles() -> tuple[Candle, ...]:
    return (
        Candle(
            timestamp=datetime(2026, 11, 7, 9, 12, tzinfo=UTC),
            open=1.1300,
            high=1.1304,
            low=1.1298,
            close=1.1302,
            volume=0.0,
        ),
        Candle(
            timestamp=datetime(2026, 11, 7, 9, 13, tzinfo=UTC),
            open=1.1302,
            high=1.1306,
            low=1.1301,
            close=1.1305,
            volume=0.0,
        ),
    )


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_saves_one_immutable_iq_option_demo_analysis_record(
    tmp_path: Path,
) -> None:
    repository = IqOptionDemoAnalysisRepository(tmp_path)
    record_path = repository.save(
        signal=create_signal(),
        candles=create_candles(),
        recorded_at=datetime(2026, 11, 7, 9, 15, tzinfo=UTC),
    )

    payload = read_json(record_path)

    assert record_path.parent == tmp_path
    assert record_path.suffix == ".json"
    assert record_path.name.startswith("iq-demo-20261107-091500-000000-eurusd-otc-")
    assert payload == {
        "schemaVersion": 1,
        "recordId": record_path.stem,
        "recordedAt": "2026-11-07T09:15:00+00:00",
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "analysis": {
            "symbol": "EURUSD-OTC",
            "timeframe": "1m",
            "timestamp": "2026-11-07T09:14:00+00:00",
            "direction": "NEUTRAL",
            "score": 20,
            "reasons": ["No EMA 9/21 crossover detected"],
            "strategy": "ema_crossover",
            "indicators": {
                "fastEmaPeriod": 9,
                "slowEmaPeriod": 21,
            },
        },
        "candles": [
            {
                "timestamp": "2026-11-07T09:12:00+00:00",
                "open": 1.1300,
                "high": 1.1304,
                "low": 1.1298,
                "close": 1.1302,
                "volume": 0.0,
                "closed": True,
            },
            {
                "timestamp": "2026-11-07T09:13:00+00:00",
                "open": 1.1302,
                "high": 1.1306,
                "low": 1.1301,
                "close": 1.1305,
                "volume": 0.0,
                "closed": True,
            },
        ],
    }


def test_creates_the_storage_directory_when_it_does_not_exist(
    tmp_path: Path,
) -> None:
    root_directory = tmp_path / "nested" / "iq-option-demo-analyses"
    repository = IqOptionDemoAnalysisRepository(root_directory)

    record_path = repository.save(
        signal=create_signal(),
        candles=create_candles(),
        recorded_at=datetime(2026, 11, 7, 9, 15, tzinfo=UTC),
    )

    assert root_directory.is_dir()
    assert record_path.is_file()


def test_rejects_an_empty_candle_collection(tmp_path: Path) -> None:
    repository = IqOptionDemoAnalysisRepository(tmp_path)

    with pytest.raises(
        ValueError,
        match="candles must contain at least one closed candle",
    ):
        repository.save(
            signal=create_signal(),
            candles=(),
            recorded_at=datetime(2026, 11, 7, 9, 15, tzinfo=UTC),
        )


def test_rejects_a_naive_record_timestamp(tmp_path: Path) -> None:
    repository = IqOptionDemoAnalysisRepository(tmp_path)

    with pytest.raises(ValueError, match="recorded_at must be timezone-aware"):
        repository.save(
            signal=create_signal(),
            candles=create_candles(),
            recorded_at=datetime(2026, 11, 7, 9, 15),
        )