import json

import pytest

from app.cli import get_iq_option_demo_analysis_history


class FakeAnalysisRepository:
    def __init__(self) -> None:
        self.requested_limits: list[int] = []
        self.requested_record_ids: list[str] = []

    def list_summaries(
        self,
        limit: int,
    ) -> tuple[dict[str, object], ...]:
        self.requested_limits.append(limit)

        return (
            {
                "recordId": "iq-demo-test-record",
                "recordedAt": "2026-11-07T09:36:08+00:00",
                "source": "iq_option_demo",
                "venue": "iq",
                "accountMode": "PRACTICE",
                "symbol": "EURUSD-OTC",
                "timeframe": "1m",
                "timestamp": "2026-11-07T09:35:00+00:00",
                "direction": "NEUTRAL",
                "score": 20,
                "strategy": "ema_crossover",
            },
        )

    def get_record(self, record_id: str) -> dict[str, object]:
        self.requested_record_ids.append(record_id)

        return {
            "schemaVersion": 1,
            "recordId": record_id,
            "recordedAt": "2026-11-07T09:36:08+00:00",
            "source": "iq_option_demo",
            "venue": "iq",
            "accountMode": "PRACTICE",
            "analysis": {
                "symbol": "EURUSD-OTC",
                "timeframe": "1m",
                "timestamp": "2026-11-07T09:35:00+00:00",
                "direction": "NEUTRAL",
                "score": 20,
                "reasons": ["No EMA 9/21 crossover detected"],
                "strategy": "ema_crossover",
                "indicators": {
                    "fastEmaPeriod": 9,
                    "slowEmaPeriod": 21,
                },
            },
            "candles": [],
        }


def test_lists_recent_iq_option_demo_analysis_summaries() -> None:
    repository = FakeAnalysisRepository()

    payload = (
        get_iq_option_demo_analysis_history
        .list_iq_option_demo_analysis_history(
            limit=10,
            repository=repository,
        )
    )

    assert repository.requested_limits == [10]
    assert payload == {
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "records": [
            {
                "recordId": "iq-demo-test-record",
                "recordedAt": "2026-11-07T09:36:08+00:00",
                "source": "iq_option_demo",
                "venue": "iq",
                "accountMode": "PRACTICE",
                "symbol": "EURUSD-OTC",
                "timeframe": "1m",
                "timestamp": "2026-11-07T09:35:00+00:00",
                "direction": "NEUTRAL",
                "score": 20,
                "strategy": "ema_crossover",
            }
        ],
    }


def test_returns_one_complete_iq_option_demo_analysis_record() -> None:
    repository = FakeAnalysisRepository()

    payload = (
        get_iq_option_demo_analysis_history
        .get_iq_option_demo_analysis_record(
            record_id="iq-demo-test-record",
            repository=repository,
        )
    )

    assert repository.requested_record_ids == ["iq-demo-test-record"]
    assert payload["recordId"] == "iq-demo-test-record"
    assert payload["analysis"] == {
        "symbol": "EURUSD-OTC",
        "timeframe": "1m",
        "timestamp": "2026-11-07T09:35:00+00:00",
        "direction": "NEUTRAL",
        "score": 20,
        "reasons": ["No EMA 9/21 crossover detected"],
        "strategy": "ema_crossover",
        "indicators": {
            "fastEmaPeriod": 9,
            "slowEmaPeriod": 21,
        },
    }


def test_writes_history_json_to_stdout(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_payload = {
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "records": [],
    }

    monkeypatch.setattr(
        get_iq_option_demo_analysis_history,
        "list_iq_option_demo_analysis_history",
        lambda limit: expected_payload,
    )

    exit_code = get_iq_option_demo_analysis_history.main(["--limit", "5"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert json.loads(captured.out) == expected_payload
    assert captured.err == ""


def test_writes_not_found_error_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def missing_record(record_id: str) -> dict[str, object]:
        raise FileNotFoundError(
            f"IQ Option DEMO analysis record was not found: {record_id}"
        )

    monkeypatch.setattr(
        get_iq_option_demo_analysis_history,
        "get_iq_option_demo_analysis_record",
        missing_record,
    )

    exit_code = get_iq_option_demo_analysis_history.main(
        [
            "--record-id",
            "iq-demo-20261107-091500-000000-eurusd-otc-abcdef1234",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "error": {
            "code": "IQ_OPTION_DEMO_ANALYSIS_NOT_FOUND",
            "message": (
                "IQ Option DEMO analysis record was not found: "
                "iq-demo-20261107-091500-000000-eurusd-otc-abcdef1234"
            ),
        },
    }