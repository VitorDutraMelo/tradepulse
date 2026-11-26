import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.cli.get_iq_option_demo_m5_signal import (
    JsonArgumentParser,
    error_to_payload,
)

DEFAULT_M5_VALIDATION_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "data/iq-option-demo-m5-validations"
)

RECORD_ID_PATTERN = re.compile(
    r"^iq-demo-m5-\d{8}-\d{6}-\d{6}-[a-z0-9-]+-[a-f0-9]{10}$"
)


def load_record(record_path: Path) -> dict[str, Any]:
    payload = json.loads(record_path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("IQ Option DEMO M5 validation record is invalid")

    return payload


def get_required_string(
    payload: dict[str, Any],
    field_name: str,
) -> str:
    value = payload.get(field_name)

    if not isinstance(value, str) or not value:
        raise ValueError(
            f"IQ Option DEMO M5 validation {field_name} is invalid"
        )

    return value


def get_optional_string(
    payload: dict[str, Any],
    field_name: str,
    default: str,
) -> str:
    value = payload.get(field_name)

    return value if isinstance(value, str) and value else default


def get_object(
    payload: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    value = payload.get(field_name)

    return value if isinstance(value, dict) else {}


def get_nested_object(
    payload: dict[str, Any],
    field_name: str,
) -> dict[str, Any]:
    direct = get_object(payload, field_name)

    if direct:
        return direct

    validation = get_object(payload, "validation")
    nested = validation.get(field_name)

    return nested if isinstance(nested, dict) else {}


def get_nested_string(
    payload: dict[str, Any],
    field_name: str,
    default: str,
) -> str:
    direct = payload.get(field_name)

    if isinstance(direct, str) and direct:
        return direct

    validation = get_object(payload, "validation")
    nested = validation.get(field_name)

    return nested if isinstance(nested, str) and nested else default


def to_summary(record: dict[str, Any]) -> dict[str, Any]:
    decision = get_nested_object(record, "decision")
    outcome = get_object(record, "outcome")

    return {
        "recordId": get_required_string(record, "recordId"),
        "recordedAt": get_required_string(record, "recordedAt"),
        "symbol": get_nested_string(record, "symbol", "UNKNOWN"),
        "timeframe": get_nested_string(record, "timeframe", "5m"),
        "candidateAction": get_optional_string(
            decision,
            "candidateAction",
            "WAIT",
        ),
        "m5CandidateAction": get_optional_string(
            decision,
            "m5CandidateAction",
            get_optional_string(decision, "candidateAction", "WAIT"),
        ),
        "actionability": get_optional_string(
            decision,
            "actionability",
            "UNKNOWN",
        ),
        "theoreticalEntryTime": get_optional_string(
            decision,
            "theoreticalEntryTime",
            "",
        ),
        "theoreticalExpirationTime": get_optional_string(
            decision,
            "theoreticalExpirationTime",
            "",
        ),
        "outcome": {
            "status": get_optional_string(
                outcome,
                "status",
                "PENDING",
            ),
            "settledAt": outcome.get("settledAt"),
            "settlementPrice": outcome.get("settlementPrice"),
        },
    }


def list_record_paths(
    directory: Path,
) -> list[Path]:
    if not directory.exists():
        return []

    if not directory.is_dir():
        raise ValueError(
            "IQ Option DEMO M5 validation directory is invalid"
        )

    return sorted(
        directory.glob("iq-demo-m5-*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def get_record_path(
    directory: Path,
    record_id: str,
) -> Path:
    if not RECORD_ID_PATTERN.fullmatch(record_id):
        raise ValueError("IQ Option DEMO M5 validation record ID is invalid")

    record_path = directory / f"{record_id}.json"

    if not record_path.is_file():
        raise ValueError("IQ Option DEMO M5 validation record was not found")

    return record_path


def list_m5_validations(
    limit: int,
    directory: Path = DEFAULT_M5_VALIDATION_DIRECTORY,
) -> dict[str, Any]:
    if limit < 1 or limit > 100:
        raise ValueError("limit must be between 1 and 100")

    records = [
        to_summary(load_record(record_path))
        for record_path in list_record_paths(directory)[:limit]
    ]

    return {
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "records": records,
    }


def get_m5_validation_record(
    record_id: str,
    directory: Path = DEFAULT_M5_VALIDATION_DIRECTORY,
) -> dict[str, Any]:
    record = load_record(get_record_path(directory, record_id))

    return {
        "source": "iq_option_demo",
        "venue": "iq",
        "accountMode": "PRACTICE",
        "record": record,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = JsonArgumentParser(
        description=(
            "List or retrieve theoretical IQ Option DEMO "
            "M5 plus M15 validation records."
        ),
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--record-id")

    try:
        arguments = parser.parse_args(argv)

        if arguments.record_id:
            payload = get_m5_validation_record(arguments.record_id)
        else:
            payload = list_m5_validations(arguments.limit)
    except (
        OSError,
        PermissionError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        print(json.dumps(error_to_payload(error)), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
