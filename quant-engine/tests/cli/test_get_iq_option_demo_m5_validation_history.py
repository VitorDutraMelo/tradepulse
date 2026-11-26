import json
from pathlib import Path

from app.cli import get_iq_option_demo_m5_validation_history as history


def create_record(record_id: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "recordId": record_id,
        "recordedAt": "2026-11-21T16:00:02+00:00",
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "symbol": "GBPUSD-OTC",
        "timeframe": "5m",
        "decision": {
            "candidateAction": "CALL",
            "m5CandidateAction": "CALL",
            "actionability": "NOT_ACTIONABLE_LATE",
            "theoreticalEntryTime": "2026-11-21T16:00:00+00:00",
            "theoreticalExpirationTime": "2026-11-21T16:05:00+00:00",
        },
        "outcome": {
            "status": "PENDING",
            "settledAt": None,
            "settlementPrice": None,
        },
    }


def write_record(
    directory: Path,
    record: dict[str, object],
) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    record_id = str(record["recordId"])

    (directory / f"{record_id}.json").write_text(
        json.dumps(record),
        encoding="utf-8",
    )


def test_lists_empty_validation_history(
    tmp_path: Path,
) -> None:
    payload = history.list_m5_validations(
        limit=20,
        directory=tmp_path,
    )

    assert payload["source"] == "iq_option_demo"
    assert payload["venue"] == "iq"
    assert payload["accountMode"] == "PRACTICE"
    assert payload["records"] == []


def test_lists_m5_validation_summary(
    tmp_path: Path,
) -> None:
    record_id = (
        "iq-demo-m5-20261121-160002-000000-"
        "gbpusd-otc-0123456789"
    )
    write_record(tmp_path, create_record(record_id))

    payload = history.list_m5_validations(
        limit=20,
        directory=tmp_path,
    )

    assert len(payload["records"]) == 1

    summary = payload["records"][0]

    assert summary["recordId"] == record_id
    assert summary["symbol"] == "GBPUSD-OTC"
    assert summary["candidateAction"] == "CALL"
    assert summary["outcome"]["status"] == "PENDING"


def test_returns_complete_m5_validation_record(
    tmp_path: Path,
) -> None:
    record_id = (
        "iq-demo-m5-20261121-160002-000000-"
        "gbpusd-otc-0123456789"
    )
    expected_record = create_record(record_id)
    write_record(tmp_path, expected_record)

    payload = history.get_m5_validation_record(
        record_id,
        directory=tmp_path,
    )

    assert payload["record"] == expected_record


def test_rejects_invalid_record_id(
    tmp_path: Path,
) -> None:
    try:
        history.get_m5_validation_record(
            "../not-a-record",
            directory=tmp_path,
        )
    except ValueError as error:
        assert "record ID is invalid" in str(error)
    else:
        raise AssertionError("Expected invalid record ID to fail")
